import json
import re

async def fix_agent_executor():
    with open(r'c:\Users\savy\Desktop\New folder\Koe Syndicate-main-copy for further\lead_finder\agent_executor.py', 'r') as f:
        content = f.read()
        
    replacement = '''
            # After run_async completes, try to extract businesses from session state
            if session and session.state and "final_merged_leads" in session.state:
                import re, json
                merged_leads_text = session.state["final_merged_leads"]
                json_match = re.search(r"`json\\s*([\\s\\S]*?)\\s*`", merged_leads_text)
                if json_match:
                    try:
                        parsed_data = json.loads(json_match.group(1))
                        if isinstance(parsed_data, list):
                            final_result["businesses"] = parsed_data
                            final_result["count"] = len(parsed_data)
                            logger.info(f"Task {context.task_id}: Extracted {len(parsed_data)} businesses from session state")
                    except Exception as e:
                        logger.error(f"Failed to parse JSON from session state: {e}")
            
            task_updater.add_artifact(
'''
    content = content.replace('            task_updater.add_artifact(', replacement)
    
    with open(r'c:\Users\savy\Desktop\New folder\Koe Syndicate-main-copy for further\lead_finder\agent_executor.py', 'w') as f:
        f.write(content)

import asyncio
asyncio.run(fix_agent_executor())
