from strands import Agent, tool
from strands_tools import rss
from strands_tools import http_request, retrieve
from mcp.client.streamable_http import streamable_http_client
from strands.tools.mcp.mcp_client import MCPClient
import json
import html2text
import feedparser

# Define a security and compliance focused system prompt

AGENT_PROMPT = """You are a security and compliance expert that helps users understand difference compliance frameworks, such as HIPPA, NIST, PCI, and etc. 

You have the following capabilities:
1. Use the mcp_client to provide information about anything related to AWS documentation, AWS APIs, and best practices
2.  If a user wants information on specific compliance frameworks, give then an overview of what that compliance framework is and provide them a condensed summary. 
    - Use the common_compliance_frameworks to provide information about what compliance frameworks are the most common. 
    - When displaying responses, display them in a bulleted list. 
3. You provide the most recent security news from the linked news feed.
    - Provide a bulleted list of the titles of the publishings to that feed. 
    - In addition to providing the title, include a hyperlink to URL of the news 
    - Use the rss tool to get this from http://blogs.aws.amazon.com/security/blog/feed/recentPosts.rss
    - Do a max of 3 entries, unless the user requests a specific amount. Have the maximum be 10. 
4. Use the retrieve tool to retrieve information about the image and PDF that is stored regarding SHIP and Security Hub

"""

@tool
def security_compliance_list() -> list:
    
    """
    Get a list of common security and  compliance frameworks that is used in the IT industry. 
    """

    security_compliance_standards = ["CIS Critical Security Controls", "PCI DSS", "NIST Cybersecurity Framework (CSF)", "ISO", "HIPPA", "HITRUST", "FedRAMP"]

    return security_compliance_standards



    
def lambda_handler(event, context):

    #Sets up an MCP connection using Streamable HTTP transport
    mcp_client = MCPClient(
        lambda: streamable_http_client("https://knowledge-mcp.global.api.aws")
    )


    with mcp_client:

        #Define tools available for agent to use along with the MCP
        tools_mcp = mcp_client.list_tools_sync()
        tools_mcp += [security_compliance_list, rss, retrieve]
        
        # Create an agent with tools 
        agent = Agent(
           model = "us.amazon.nova-micro-v1:0",
           system_prompt = AGENT_PROMPT, 
           tools = tools_mcp
        )

        body = json.loads(event['body'])
        response = agent(body['prompt'])

    return {
        'statusCode': 200,
        'body': json.dumps({
            'response': str(response)
        })
    }


"""
curl -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Can you tell me about IAM APIs?"}' | jq
"""