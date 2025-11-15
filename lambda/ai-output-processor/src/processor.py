import json
import os
import requests
import logging
import re
import boto3
import traceback
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Common response helper
def create_response(status_code: int, body: Any) -> Dict[str, Any]:
    """Helper to create standardized HTTP responses"""
    return {
        'statusCode': status_code,
        'body': json.dumps(body) if isinstance(body, dict) else body
    }

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_client = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'eu-west-1'))
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'eu-west-1'))

def get_secrets():
    """
    Retrieve all secrets from AWS Secrets Manager (JSON bundle)
    """
    try:
        response = secrets_client.get_secret_value(SecretId='chatops/secrets')
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Failed to retrieve secrets from Secrets Manager: {e}")
        raise

def get_telegram_bot_token():
    """
    Retrieve Telegram bot token from AWS Secrets Manager
    """
    secrets = get_secrets()
    return secrets['telegram_bot_token']

@dataclass
class ProcessingConfig:
    """Configuration for output processing"""
    enable_ai_processing: bool = False
    max_message_length: int = 3500
    max_messages: int = 10

class TerraformOutputProcessor:
    """Processes Terraform outputs with smart summarization and formatting"""

    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.telegram_bot_token = get_telegram_bot_token()

    def process_output(self, raw_output: str, command: str, chat_id: str, token: Optional[str] = None, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Main processing function with hybrid approach:
        - Regex for structured data extraction
        - LLM only for errors or high-risk analysis
        """
        try:
            logger.info(f"Processing {command} output for chat {chat_id}")

            # Clean and sanitize output
            cleaned_output = self.sanitize_output(raw_output)

            logger.info(f"Raw output length: {len(raw_output)}")
            logger.info(f"Cleaned output length: {len(cleaned_output)}")

            # Task 1: Check for errors (use LLM if found)
            error_text = self.extract_errors(cleaned_output)
            if error_text:
                logger.info("Errors detected - using LLM for error summarization")
                error_summary = self.summarize_error_with_ai(error_text)
                if error_summary:
                    processed_messages = self.format_error_summary(error_summary, command)
                    processing_method = "regex+error_ai"
                else:
                    # Fallback if LLM fails
                    logger.warning("LLM error summarization failed, using simple error format")
                    processed_messages = self.format_error_summary(error_text[:500], command)
                    processing_method = "regex_only"
            else:
                # No errors - continue with normal processing
                if command == 'destroy':
                    # Extract plan summary
                    plan_summary = self.extract_plan_summary(cleaned_output)
                    if plan_summary:
                        # Task 2: Check if high-risk resources are affected
                        if self.has_high_risk_resources(cleaned_output, plan_summary):
                            logger.info("High-risk resources detected - using LLM for risk analysis")
                            risk_analysis = self.analyze_risk_with_ai(cleaned_output, plan_summary)
                            if risk_analysis:
                                processed_messages = self.format_plan_with_risk_analysis(plan_summary, risk_analysis, cleaned_output)
                                processing_method = "regex+risk_ai"
                            else:
                                # Fallback if LLM fails
                                logger.warning("LLM risk analysis failed, using regex-only format")
                                processed_messages = self.format_plan_with_regex(plan_summary, cleaned_output)
                                processing_method = "regex_only"
                        else:
                            # Low-risk plan - use regex extraction only
                            logger.info("Low-risk plan - using regex extraction only")
                            processed_messages = self.format_plan_with_regex(plan_summary, cleaned_output)
                            processing_method = "regex_only"
                    else:
                        # No plan summary found - fallback to simple processing
                        logger.warning("Could not extract plan summary, using simple processing")
                        processed_messages = self.process_simple(cleaned_output, command)
                        processing_method = "regex_only"

                elif command == 'confirm_destroy':
                    # Extract apply result
                    apply_result = self.extract_apply_result(cleaned_output)
                    if apply_result:
                        if apply_result['status'] == 'failed':
                            # Error already handled above, but double-check
                            error_text = self.extract_errors(cleaned_output)
                            if error_text:
                                logger.info("Apply failed with errors - using LLM for error summarization")
                                error_summary = self.summarize_error_with_ai(error_text)
                                if error_summary:
                                    processed_messages = self.format_error_summary(error_summary, command)
                                    processing_method = "regex+error_ai"
                                else:
                                    processed_messages = self.format_apply_result(apply_result, cleaned_output)
                                    processing_method = "regex_only"
                            else:
                                processed_messages = self.format_apply_result(apply_result, cleaned_output)
                                processing_method = "regex_only"
                        else:
                            # Success - use regex extraction only
                            processed_messages = self.format_apply_result(apply_result, cleaned_output)
                            processing_method = "regex_only"
                    else:
                        # Fallback to simple processing
                        logger.warning("Could not extract apply result, using simple processing")
                        processed_messages = self.process_simple(cleaned_output, command)
                        processing_method = "regex_only"

                elif command == 'status':
                    # Status is always simple - use regex extraction
                    processed_messages = self.format_status_with_regex(cleaned_output)
                    processing_method = "regex_only"

                else:
                    # Unknown command - fallback to simple processing
                    processed_messages = self.process_simple(cleaned_output, command)
                    processing_method = "regex_only"

            logger.info(f"Processing method: {processing_method}")

            # Send messages to Telegram
            # For destroy plans, add Confirm Destroy button to the last message
            if command == 'destroy' and project:
                # Add button to last message
                results = self.send_telegram_messages(chat_id, processed_messages[:-1])
                if processed_messages:
                    # Send last message with button
                    last_message = processed_messages[-1]
                    result = self.send_telegram_message_with_button(chat_id, last_message, command, project)
                    results.append(result)
            else:
                results = self.send_telegram_messages(chat_id, processed_messages)

            return create_response(200, {
                'success': True,
                'messages_sent': len(results),
                'processing_method': processing_method
            })

        except Exception as e:
            logger.error(f"Error processing output: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return create_response(500, {'error': 'Processing failed'})

    def sanitize_output(self, text: str) -> str:
        """Sanitize output by removing secrets and cleaning up formatting"""
        if not text:
            return ""

        try:
            # Remove common secret patterns
            secret_patterns = [
                r"gh[o|p]_[A-Za-z0-9]{20,}",  # GitHub tokens
                r"AKIA[0-9A-Z]{16}",          # AWS access keys
                r"ASIA[0-9A-Z]{16}",          # AWS session tokens
                r"(?i)secret[^\n\r]{0,50}",   # Generic secrets
                r"x-api-key:[^\n\r]+",        # API keys
                r"password[^\n\r]{0,50}",     # Passwords
                r"token[^\n\r]{0,50}",        # Tokens
            ]

            scrubbed = text
            for pattern in secret_patterns:
                scrubbed = re.sub(pattern, "[REDACTED]", scrubbed, flags=re.IGNORECASE)

            # Clean up formatting
            scrubbed = re.sub(r"\n{3,}", "\n\n", scrubbed)  # Collapse multiple newlines
            scrubbed = scrubbed.strip()

            # Remove duplicate sections (common in Terraform output)
            scrubbed = self.remove_duplicate_sections(scrubbed)

            return scrubbed

        except Exception as e:
            logger.warning(f"Error sanitizing output: {e}")
            return text[:self.config.max_message_length]

    def remove_duplicate_sections(self, text: str) -> str:
        """Remove duplicate resource lists and action summaries"""
        lines = text.split('\n')
        seen_sections = set()
        result_lines = []

        current_section = []
        in_list = False

        for line in lines:
            # Detect section headers
            if any(phrase in line.lower() for phrase in [
                'terraform will destroy',
                'terraform will perform',
                'will destroy the following',
                'will perform the following'
            ]):
                section_key = line.lower().strip()
                if section_key not in seen_sections:
                    seen_sections.add(section_key)
                    if current_section:
                        result_lines.extend(current_section)
                    current_section = [line]
                    in_list = True
                else:
                    # Skip duplicate section
                    in_list = False
                    current_section = []
            elif in_list:
                # Check if line is a list item (starts with number or resource type)
                if re.match(r'^\d+\.\s+|^\s*-', line) or any(res_type in line.lower() for res_type in [
                    'aws_', 'resource', 'module', 'data'
                ]):
                    current_section.append(line)
                elif line.strip() == '':
                    # End of list
                    if current_section:
                        result_lines.extend(current_section)
                        result_lines.append(line)
                    current_section = []
                    in_list = False
                else:
                    # Non-list content, keep it
                    if current_section:
                        result_lines.extend(current_section)
                        current_section = []
                    result_lines.append(line)
                    in_list = False
            else:
                result_lines.append(line)

        # Add remaining section
        if current_section:
            result_lines.extend(current_section)

        return '\n'.join(result_lines)

    def _invoke_bedrock(self, prompt: str) -> str:
        """Helper method to invoke Bedrock with a prompt"""
        model_id = os.environ.get('AI_MODEL_ID', 'amazon.titan-text-express-v1')
        try:
            request_body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": int(os.environ.get('AI_MAX_TOKENS', '1000')),
                    "temperature": 0.7,
                    "topP": 0.9
                }
            }

            logger.info(f"Invoking Bedrock model: {model_id}, prompt length: {len(prompt)}")

            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )

            logger.info(f"Bedrock response status: {response.get('ResponseMetadata', {}).get('HTTPStatusCode')}")

            # Parse response
            response_body = json.loads(response['body'].read())

            if 'results' not in response_body or len(response_body['results']) == 0:
                logger.warning("Bedrock returned empty results")
                return ""

            summary = response_body['results'][0]['outputText'].strip()
            logger.info(f"AI summary generated, length: {len(summary)}")
            return summary

        except Exception as e:
            logger.error(f"Bedrock invocation failed: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return ""

    def summarize_error_with_ai(self, error_text: str) -> str:
        """
        Task 1: Use LLM to summarize unstructured errors

        This is the CORRECT use of LLM: high-level comprehension of unstructured error text.
        The LLM's job is to make the error human-readable and actionable.
        The bot code has already extracted the error text - no counting or extraction needed.
        """
        # Truncate error text to avoid token limits
        truncated_error = error_text[:3000]

        prompt = f"""You are a DevOps assistant. The following is a raw Terraform error message. Summarize this error into a clear, human-readable, and actionable insight for the user. Explain what failed and why.

Error Message:
{truncated_error}

Provide a concise summary (2-3 sentences) explaining:
1. What failed
2. Why it failed
3. What the user should do next"""

        return self._invoke_bedrock(prompt)

    def analyze_risk_with_ai(self, plan_text: str, plan_summary: Dict[str, int]) -> str:
        """
        Task 2: Use LLM to analyze plan for risk

        IMPORTANT: The plan_summary counts are PRE-EXTRACTED by bot code (regex).
        The LLM must NOT attempt to count or recalculate these numbers.
        The LLM's ONLY job is high-level comprehension and risk analysis.
        """
        # Truncate plan text to avoid token limits
        truncated_plan = plan_text[:4000]

        prompt = f"""You are a senior DevOps engineer. Analyze the following Terraform plan for risk.

CRITICAL: The plan summary below was already extracted by automated code. Do NOT attempt to count or recalculate these numbers. Your ONLY task is to analyze the risk level and identify critical resources.

Pre-extracted Plan Summary: {plan_summary['to_add']} to add, {plan_summary['to_change']} to change, {plan_summary['to_destroy']} to destroy

Terraform Plan Text:
{truncated_plan}

Your task is to provide a concise risk analysis (2-3 sentences) focusing on:
1. Most critical or dangerous resources being changed/destroyed (e.g., databases, IAM roles, load balancers)
2. Potential impact of these changes
3. Overall risk level (high/medium/low)

If the plan is low-risk, simply state that. Do NOT count resources - use the pre-extracted summary above."""

        return self._invoke_bedrock(prompt)

    def format_plan_with_regex(self, plan_summary: Dict[str, int], text: str) -> List[str]:
        """Format destroy plan using regex extraction only (no LLM)"""
        header = "💥 **Destroy Plan Summary**"
        summary_line = f"Plan: {plan_summary['to_add']} to add, {plan_summary['to_change']} to change, {plan_summary['to_destroy']} to destroy"

        # Extract resource types using existing count_resources method
        resource_counts = self.count_resources(text)

        lines = [header, "", summary_line, ""]

        if resource_counts:
            lines.append("Resource breakdown:")
            for res_type, count in sorted(resource_counts.items()):
                lines.append(f"- {res_type}: {count}")
            lines.append("")

        lines.append("⚠️ This is only a plan - no resources have been destroyed yet.")

        full_message = '\n'.join(lines)
        return self.split_message(full_message)

    def format_plan_with_risk_analysis(self, plan_summary: Dict[str, int], risk_analysis: str, text: str) -> List[str]:
        """Format destroy plan with LLM risk analysis"""
        header = "💥 **Destroy Plan Summary**"
        summary_line = f"Plan: {plan_summary['to_add']} to add, {plan_summary['to_change']} to change, {plan_summary['to_destroy']} to destroy"

        # Extract resource types
        resource_counts = self.count_resources(text)

        lines = [header, "", summary_line, ""]

        if resource_counts:
            lines.append("Resource breakdown:")
            for res_type, count in sorted(resource_counts.items()):
                lines.append(f"- {res_type}: {count}")
            lines.append("")

        # Add risk analysis from LLM
        if risk_analysis:
            lines.append("⚠️ **Risk Analysis:**")
            lines.append(risk_analysis)
            lines.append("")

        lines.append("⚠️ This is only a plan - no resources have been destroyed yet.")

        full_message = '\n'.join(lines)
        return self.split_message(full_message)

    def format_apply_result(self, apply_result: Dict[str, Any], text: str) -> List[str]:
        """Format apply/destroy results using regex extraction (no LLM)"""
        header = "🚀 **Destroy Apply Results**"

        lines = [header, ""]

        if apply_result['status'] == 'success':
            count = apply_result.get('resources_destroyed')
            if count is not None:
                lines.append(f"✅ Destroy Successful")
                lines.append(f"Resources destroyed: {count}")
            else:
                lines.append(f"✅ Destroy Successful")
        else:
            lines.append("❌ Destroy Failed")

        full_message = '\n'.join(lines)
        return self.split_message(full_message)

    def format_status_with_regex(self, text: str) -> List[str]:
        """Format status command using regex extraction (no LLM)"""
        header = "🔍 **Terraform Status Summary**"

        resource_counts = self.count_resources(text)
        total = sum(resource_counts.values()) if resource_counts else 0

        lines = [header, ""]

        if total > 0:
            lines.append(f"Total resources: {total}")
            if resource_counts:
                lines.append("")
                for res_type, count in sorted(resource_counts.items()):
                    lines.append(f"- {res_type}: {count}")
        else:
            lines.append("The state file is empty. No resources are represented.")

        full_message = '\n'.join(lines)
        return self.split_message(full_message)

    def format_error_summary(self, error_summary: str, command: str) -> List[str]:
        """Format error summary from LLM"""
        headers = {
            'status': "🔍 **Terraform Status Error**",
            'destroy': "💥 **Destroy Plan Error**",
            'confirm_destroy': "🚀 **Destroy Apply Error**"
        }

        header = headers.get(command, "❌ **Terraform Error**")

        lines = [header, "", error_summary]

        full_message = '\n'.join(lines)
        return self.split_message(full_message)

    def process_simple(self, text: str, command: str) -> List[str]:
        """Simple processing without AI - includes basic parsing and deduplication"""
        headers = {
            'status': "🔍 **Terraform Status**",
            'destroy': "💥 **Destroy Plan**",
            'confirm_destroy': "🚀 **Destroy Apply**"
        }

        header = headers.get(command, "✅ **Terraform Result**")

        # Parse and structure the output
        structured = self.parse_terraform_output(text, command)

        # Truncate if too long
        if len(structured) > self.config.max_message_length:
            structured = structured[:self.config.max_message_length] + "\n\n... (truncated)"

        # Format with code block
        formatted_text = f"{header}\n\n{structured}"
        return self.split_message(formatted_text)

    def parse_terraform_output(self, text: str, command: str) -> str:
        """Parse Terraform output to extract structured information"""
        if not text:
            return text

        # Remove duplicates first
        deduped = self.remove_duplicate_sections(text)

        # Check for apply completion status (for confirm_destroy)
        completion_status = None
        if command == 'confirm_destroy':
            # Look for apply completion indicators
            if re.search(r'Apply complete!|Destroy complete!|resources destroyed', deduped, re.IGNORECASE):
                completion_status = "✅ **Destruction completed successfully**"
                # Extract resource count if available
                match = re.search(r'(\d+)\s+resource\(s\)\s+(?:were|will be)?\s+destroyed', deduped, re.IGNORECASE)
                if match:
                    completion_status += f" - {match.group(1)} resource(s) destroyed"
            elif re.search(r'Error:|Failed|failed', deduped, re.IGNORECASE):
                completion_status = "❌ **Destruction failed** - see errors below"
            elif re.search(r'Terraform will perform|will be destroyed', deduped, re.IGNORECASE):
                # This is still plan output, not apply results
                completion_status = "⚠️ **Note:** This appears to be plan output, not actual apply results"

        # Extract resource counts and types
        resource_counts = self.count_resources(deduped)

        # Build structured output
        lines = []

        # Add completion status for confirm_destroy
        if completion_status:
            lines.append(completion_status)
            lines.append("")

        # Add summary if we have resource counts
        if resource_counts:
            total = sum(resource_counts.values())
            if command == 'confirm_destroy':
                lines.append(f"**Resources Destroyed:** {total} resource(s)")
            else:
                lines.append(f"**Summary:** {total} resource(s) to be affected")
            lines.append("")
            for res_type, count in sorted(resource_counts.items()):
                lines.append(f"  • {res_type}: {count}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # For confirm_destroy, prefer showing actual results over plan
        if command == 'confirm_destroy':
            # Look for the apply results section (comes after plan)
            apply_section = self.extract_apply_results(deduped)
            if apply_section:
                lines.append("**Destruction Results:**")
                lines.append("")
                lines.append(apply_section)
                return '\n'.join(lines)

        # Add the actual resource list (first occurrence only)
        resource_lines = []
        in_resource_section = False
        seen_resources = set()

        for line in deduped.split('\n'):
            # Detect resource lines
            if re.search(r'(aws_|resource|module\.|data\.)', line, re.IGNORECASE):
                resource_key = re.sub(r'\d+\.\s+', '', line).strip().lower()
                if resource_key not in seen_resources:
                    seen_resources.add(resource_key)
                    resource_lines.append(line)
                    in_resource_section = True
            elif in_resource_section and line.strip() == '':
                # End of resource section
                break
            elif in_resource_section:
                resource_lines.append(line)

        if resource_lines:
            lines.extend(resource_lines)
        else:
            # Fallback to deduped text
            lines.append(deduped)

        return '\n'.join(lines)

    def extract_apply_results(self, text: str) -> str:
        """Extract the actual apply results section from Terraform output"""
        lines = text.split('\n')
        results_start = None
        results_end = None

        # Find where apply results start
        for i, line in enumerate(lines):
            if re.search(r'Apply complete!|Destroy complete!|resources destroyed', line, re.IGNORECASE):
                results_start = i
                break

        if results_start is None:
            # No clear apply results found, return empty
            return None

        # Extract from results_start to end (or next major section)
        result_lines = []
        for i in range(results_start, len(lines)):
            line = lines[i]
            # Stop if we hit another major section
            if i > results_start + 50 and re.match(r'^[A-Z]', line.strip()):
                break
            result_lines.append(line)

        return '\n'.join(result_lines[:30])  # Limit to 30 lines

    def count_resources(self, text: str) -> dict:
        """Count resources by type in Terraform output"""
        counts = {}

        # Specific resource patterns (order matters - more specific first)
        specific_patterns = {
            'AWS Instance': r'aws_instance\.[\w-]+',
            'AWS VPC': r'aws_vpc\.[\w-]+',
            'AWS Subnet': r'aws_subnet\.[\w-]+',
            'AWS Security Group': r'aws_security_group\.[\w-]+',
            'AWS Route Table': r'aws_route_table\.[\w-]+',
            'AWS Internet Gateway': r'aws_internet_gateway\.[\w-]+',
            'AWS NACL': r'aws_network_acl\.[\w-]+',
            'VPC Connection': r'aws_vpc.*connection',
            'Route': r'aws_route\.[\w-]+',
        }

        # Track all matched resource strings to avoid double-counting
        matched_resources = set()

        # Count specific resource types first
        for res_type, pattern in specific_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Use set to deduplicate matches (same resource may appear multiple times in output)
                unique_matches = set(matches)
                counts[res_type] = len(unique_matches)
                # Track these resources so we don't count them in "Other"
                matched_resources.update(unique_matches)

        # Now count "Other AWS Resources" - only resources NOT already counted
        # Find all AWS resources
        all_aws_resources = re.findall(r'(aws_\w+\.[\w-]+)', text, re.IGNORECASE)
        if all_aws_resources:
            # Deduplicate
            unique_aws_resources = set(all_aws_resources)
            # Filter out resources already counted
            other_resources = unique_aws_resources - matched_resources
            if other_resources:
                counts['Other AWS Resources'] = len(other_resources)

        # Fallback: If no AWS resources found, try generic pattern
        if not counts:
            generic_matches = re.findall(r'(\w+\.\w+)', text)
            if generic_matches:
                for match in set(generic_matches):
                    res_type = match.split('.')[0].replace('aws_', 'AWS ').title()
                    counts[res_type] = generic_matches.count(match)

        return counts

    def extract_plan_summary(self, text: str) -> Optional[Dict[str, int]]:
        """Extract plan summary: Plan: X to add, Y to change, Z to destroy"""
        match = re.search(r'Plan:\s*(\d+)\s+to\s+add,\s*(\d+)\s+to\s+change,\s*(\d+)\s+to\s+destroy', text)
        if match:
            return {
                'to_add': int(match.group(1)),
                'to_change': int(match.group(2)),
                'to_destroy': int(match.group(3))
            }
        return None

    def extract_apply_result(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract apply completion status and resource count"""
        # Look for completion indicators
        if re.search(r'Apply complete!|Destroy complete!', text, re.IGNORECASE):
            # Extract resource count - try multiple patterns
            count = None
            match1 = re.search(r'Resources:\s*(\d+)\s+destroyed', text, re.IGNORECASE)
            match2 = re.search(r'(\d+)\s+resource\(s\)\s+destroyed', text, re.IGNORECASE)
            match3 = re.search(r'Destroy\s+Complete!\s+Resources:\s*(\d+)\s+destroyed', text, re.IGNORECASE)

            if match1:
                count = int(match1.group(1))
            elif match2:
                count = int(match2.group(1))
            elif match3:
                count = int(match3.group(1))

            return {'status': 'success', 'resources_destroyed': count}

        # Check for errors
        if re.search(r'Error:|Failed|failed', text, re.IGNORECASE):
            return {'status': 'failed'}

        return None

    def extract_errors(self, text: str) -> Optional[str]:
        """Extract full error message if present"""
        # Look for Error: followed by content until double newline or end
        error_match = re.search(r'Error:.*?(?=\n\n|\Z)', text, re.DOTALL | re.IGNORECASE)
        if error_match:
            error_text = error_match.group(0).strip()
            # Also check for "Failed" patterns
            if len(error_text) < 50:  # Short match, might be incomplete
                failed_match = re.search(r'(?:Error|Failed):.*?(?=\n\n|\Z)', text, re.DOTALL | re.IGNORECASE)
                if failed_match and len(failed_match.group(0)) > len(error_text):
                    error_text = failed_match.group(0).strip()
            return error_text
        return None

    def has_high_risk_resources(self, text: str, plan_summary: Dict[str, int]) -> bool:
        """Check if plan affects high-risk resource types"""
        # Only check if there are changes or destroys
        if plan_summary['to_change'] == 0 and plan_summary['to_destroy'] == 0:
            return False

        high_risk_patterns = [
            r'aws_db_instance',
            r'aws_rds_cluster',
            r'aws_iam_role',
            r'aws_iam_policy',
            r'aws_lb\b',
            r'aws_alb\b',
            r'aws_elb\b',
            r'aws_s3_bucket',
            r'aws_route53',
        ]

        for pattern in high_risk_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def split_message(self, message: str) -> List[str]:
        """Split long messages into multiple Telegram messages"""
        if not message or not message.strip():
            logger.warning(f"split_message: received empty or whitespace-only message")
            return []

        if len(message) <= self.config.max_message_length:
            return [message]

        messages = []
        current_message = ""
        lines = message.split('\n')

        for line in lines:
            # Check if adding this line would exceed the limit
            if len(current_message) + len(line) + 1 > self.config.max_message_length:
                if current_message:
                    messages.append(current_message.strip())
                    current_message = line
                else:
                    # Line itself is too long, truncate it
                    messages.append(line[:self.config.max_message_length] + "...")
            else:
                current_message += line + '\n'

        # Add remaining content
        if current_message.strip():
            messages.append(current_message.strip())

        # Limit number of messages
        result = messages[:self.config.max_messages]
        logger.info(f"split_message: split {len(message)} char message into {len(result)} messages")
        if not result:
            logger.error(f"split_message: result is empty! message length={len(message)}, max_length={self.config.max_message_length}")
        return result

    def send_telegram_messages(self, chat_id: str, messages: List[str]) -> List[Dict[str, Any]]:
        """Send multiple messages to Telegram"""
        results = []
        logger.info(f"Attempting to send {len(messages)} messages to chat {chat_id}")

        for i, message in enumerate(messages):
            try:
                logger.info(f"Sending message {i+1}/{len(messages)}: {message[:100]}...")
                # Add message counter for multiple messages
                if len(messages) > 1:
                    message = f"**Message {i+1}/{len(messages)}**\n\n{message}"

                response = self.send_telegram_message(chat_id, message)
                logger.info(f"Message {i+1} sent successfully: {response}")
                results.append(response)

                # Small delay between messages to avoid rate limiting
                if i < len(messages) - 1:
                    import time
                    time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to send message {i+1}: {e}")
                results.append({'error': str(e)})

        logger.info(f"Sent {len(results)} messages total")
        return results

    def send_telegram_message(self, chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a single message to Telegram"""
        try:
            telegram_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"

            # Try with Markdown first
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }

            if reply_markup:
                payload['reply_markup'] = reply_markup

            response = requests.post(telegram_url, json=payload, timeout=10)

            # If Markdown fails, try with plain text
            if response.status_code == 400:
                logger.warning("Markdown parsing failed, retrying with plain text")
                payload = {
                    'chat_id': chat_id,
                    'text': text
                    # No parse_mode for plain text
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                response = requests.post(telegram_url, json=payload, timeout=10)

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            raise

    def send_telegram_message_with_button(self, chat_id: str, text: str, command: str, project: str) -> Dict[str, Any]:
        """Send a message with inline keyboard button"""
        reply_markup = None

        if command == 'destroy' and project:
            keyboard = [[
                {'text': '✅ Confirm Destroy', 'callback_data': f'confirm_destroy:{project}'},
                {'text': '❌ Cancel', 'callback_data': 'cancel'}
            ]]
            reply_markup = {'inline_keyboard': keyboard}

        return self.send_telegram_message(chat_id, text, reply_markup)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing Terraform outputs
    """
    try:
        # Parse event
        body = event.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        # Extract parameters
        raw_output = body.get('raw_output', '')
        command = body.get('command', '')
        chat_id = body.get('chat_id', '')
        token = body.get('token')
        project = body.get('project')

        # Validate required parameters
        if not all([raw_output, command, chat_id]):
            return create_response(400, {'error': 'Missing required parameters'})

        # Create processor configuration
        config = ProcessingConfig(
            enable_ai_processing=os.environ.get('ENABLE_AI_PROCESSING', 'false').lower() == 'true',
            max_message_length=int(os.environ.get('MAX_MESSAGE_LENGTH', '3500')),
            max_messages=int(os.environ.get('MAX_MESSAGES', '10'))
        )

        # Process output
        processor = TerraformOutputProcessor(config)
        result = processor.process_output(raw_output, command, chat_id, token, project)

        return result

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return create_response(500, {'error': 'Internal server error'})
