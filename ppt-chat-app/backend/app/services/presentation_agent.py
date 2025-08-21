"""
Presentation Agent using ReAct pattern with LangGraph
Intelligently plans and executes presentation modifications
"""

import logging
from typing import List, Dict, Optional, Any, Annotated
from pathlib import Path
import json

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.models import ChatMessage, SlideSpec, SlideMapping, TemplateProfile
from app.services.openai_service import openai_service
from app.services.presentation_analyzer import presentation_analyzer
from app.services.slide_composer import slide_composer
from app.services.layout_matcher import layout_matcher

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_request: str
    presentation_analysis: Dict[str, Any]
    plan: str
    actions: List[Dict[str, Any]]
    current_action: Optional[Dict[str, Any]]
    result: str
    session_id: str
    template_profile: TemplateProfile
    presentation_path: Path
    output_path: Path

class PresentationAgent:
    """ReAct agent for intelligent presentation modifications"""
    
    def __init__(self):
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the ReAct workflow graph"""
        
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("analyze_ppt", self._analyze_presentation)
        workflow.add_node("create_plan", self._create_plan)
        workflow.add_node("execute_action", self._execute_action)
        workflow.add_node("reflect_result", self._reflect_on_result)
        
        # Add edges
        workflow.set_entry_point("analyze_ppt")
        workflow.add_edge("analyze_ppt", "create_plan")
        workflow.add_edge("create_plan", "execute_action")
        workflow.add_edge("execute_action", "reflect_result")
        workflow.add_conditional_edges(
            "reflect_result",
            self._should_continue,
            {
                "continue": "execute_action",
                "end": END
            }
        )
        
        return workflow.compile()
    
    async def process_request(
        self,
        user_request: str,
        session_id: str,
        template_profile: TemplateProfile,
        presentation_path: Path,
        output_path: Path,
        chat_history: List[ChatMessage]
    ) -> Dict[str, Any]:
        """Process a user request using the ReAct agent"""
        
        initial_state = AgentState(
            messages=[],
            user_request=user_request,
            presentation_analysis={},
            plan="",
            actions=[],
            current_action=None,
            result="",
            session_id=session_id,
            template_profile=template_profile,
            presentation_path=presentation_path,
            output_path=output_path
        )
        
        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            # Return detailed debug information (ensure JSON serializable)
            analysis = final_state["presentation_analysis"].copy()
            if "layouts_used" in analysis:
                analysis["layouts_used"] = list(analysis["layouts_used"])
            
            # Convert all messages to serializable format
            thinking_steps = []
            actions_executed = []
            
            for msg in final_state["messages"]:
                if isinstance(msg, dict):
                    thinking_steps.append(msg)
                    if "Executed" in msg.get("content", ""):
                        actions_executed.append(msg)
                else:
                    # Convert non-dict messages (SystemMessage, etc.) to dict format
                    msg_dict = {
                        "role": getattr(msg, "type", getattr(msg, "role", "system")),
                        "content": getattr(msg, "content", str(msg))
                    }
                    thinking_steps.append(msg_dict)
                    if "Executed" in msg_dict.get("content", ""):
                        actions_executed.append(msg_dict)
            
            return {
                "result": final_state["result"],
                "debug_info": {
                    "analysis": analysis,
                    "plan": final_state["plan"],
                    "actions_executed": actions_executed,
                    "thinking_steps": thinking_steps,
                    "total_actions": len(actions_executed),
                    "session_id": session_id
                }
            }
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            return {
                "result": f"Error processing request: {str(e)}",
                "debug_info": {
                    "error": str(e),
                    "analysis": {},
                    "plan": "",
                    "actions_executed": [],
                    "thinking_steps": [],
                    "total_actions": 0,
                    "session_id": session_id
                }
            }
    
    async def _analyze_presentation(self, state: AgentState) -> AgentState:
        """Analyze the existing presentation structure"""
        
        logger.info("Agent: Analyzing existing presentation")
        
        # Check if there's an existing generated presentation for this session
        session_presentation = Path(state["output_path"])
        presentation_to_analyze = state["presentation_path"]
        has_existing_presentation = session_presentation.exists()
        
        if has_existing_presentation:
            # Use the existing session presentation (for follow-up requests)
            presentation_to_analyze = session_presentation
            logger.info("Found existing session presentation - will modify it")
        else:
            # Use template as the presentation to modify directly
            logger.info("No existing presentation found - will modify template directly")
        
        # Analyze the presentation
        if presentation_to_analyze.exists():
            analysis = presentation_analyzer.analyze_presentation(presentation_to_analyze)
            state["presentation_analysis"] = analysis
            # Always treat as modifiable presentation (whether template or generated)
            state["presentation_analysis"]["is_template"] = False
            
            # Create detailed summary for LLM
            summary = presentation_analyzer.get_slide_summary(analysis)
            if has_existing_presentation:
                context_msg = f"Current presentation structure:\n{summary}\n\nThis is an existing generated presentation that you can modify with edit_slide, add_slide, or delete_slide."
            else:
                context_msg = f"Current presentation structure:\n{summary}\n\nThis is the uploaded template. You can modify it directly with edit_slide, add_slide, or delete_slide."
            
            state["messages"].append({
                "role": "system", 
                "content": context_msg
            })
            
            # Update presentation path to the one we're actually modifying
            state["presentation_path"] = presentation_to_analyze
        else:
            state["presentation_analysis"] = {"total_slides": 0, "slides": [], "has_content": False}
            state["messages"].append({
                "role": "system", 
                "content": "No existing presentation found. Will create new presentation from template."
            })
        
        return state
    
    async def _create_plan(self, state: AgentState) -> AgentState:
        """Create a plan for handling the user request"""
        
        logger.info("Agent: Creating execution plan")
        
        is_template = state['presentation_analysis'].get('is_template', True)
        
        if is_template:
            planning_prompt = f"""
You are an intelligent presentation management agent. 

CRITICAL CONTEXT: NO EXISTING PRESENTATION EXISTS - ONLY A TEMPLATE

User Request: "{state['user_request']}"

Template Structure (for reference only):
{presentation_analyzer.get_slide_summary(state['presentation_analysis']) if state['presentation_analysis']['has_content'] else 'No template'}

MANDATORY FIRST ACTION: You MUST use create_presentation to generate a new presentation from the template.

Available Tools:
1. create_presentation(slides_spec) - Create entirely new presentation (REQUIRED FIRST STEP)

Since no presentation exists yet, you cannot use edit_slide, add_slide, or delete_slide.

Your plan must start with create_presentation, then the user can make follow-up requests to modify it.
"""
        else:
            planning_prompt = f"""
You are an intelligent presentation management agent. 

CONTEXT: EXISTING PRESENTATION FOUND - CAN MODIFY DIRECTLY

User Request: "{state['user_request']}"

Current Presentation:
{presentation_analyzer.get_slide_summary(state['presentation_analysis']) if state['presentation_analysis']['has_content'] else 'No existing presentation'}

Available Tools:
1. edit_slide(slide_number, new_title, new_content) - Modify an existing slide
2. add_slide(title, content, position) - Add a new slide at specified position  
3. delete_slide(slide_number) - Remove a slide
4. create_presentation(slides_spec) - Create entirely new presentation (only if replacing everything)

Analysis Guidelines:
- If user mentions specific slide content (e.g., "roadmap", "benefits", "conclusion") → find that slide and edit it
- If user says "add X to Y slide" → edit the Y slide to include X
- If user wants to modify existing content → use edit_slide
- If user wants entirely new presentation → use create_presentation
- If user wants to remove slides → use delete_slide
- If user wants additional slides → use add_slide

For edit requests like "add agentic ai in the roadmap slide":
1. Find which slide contains "roadmap" content
2. Plan to ADD "agentic ai" content to that slide (preserve existing content)
3. Preserve all other slides unchanged

IMPORTANT: When user says "add X to Y":
- PRESERVE existing content on the slide
- ADD new content as additional bullet points
- Do NOT replace or remove existing content

Create a step-by-step plan with specific slide numbers and actions.
"""

        try:
            plan_response = await openai_service.get_completion([
                {"role": "system", "content": "You are an expert presentation planner. Create detailed, actionable plans."},
                {"role": "user", "content": planning_prompt}
            ])
            
            state["plan"] = plan_response
            state["messages"].append({"role": "assistant", "content": f"Plan: {plan_response}"})
            
            # Parse plan into actions
            actions = await self._parse_plan_to_actions(plan_response, state)
            state["actions"] = actions
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            state["plan"] = f"Error creating plan: {str(e)}"
            state["actions"] = []
        
        return state
    
    async def _parse_plan_to_actions(self, plan: str, state: AgentState) -> List[Dict[str, Any]]:
        """Parse the LLM plan into executable actions"""
        
        action_prompt = f"""
Convert this plan into specific executable actions:

Plan: {plan}

User Request: {state['user_request']}

Convert to JSON array of actions. Each action should have:
- action_type: "edit_slide", "add_slide", "delete_slide", or "create_presentation"
- parameters: dict with required parameters for the action

For edit_slide parameters:
- slide_number: which slide to edit (required)
- new_title: new title (optional)
- add_content: array of bullets to ADD to existing content (use this for "add X to slide")
- replace_content: array of bullets to REPLACE all content (use only when explicitly replacing)

IMPORTANT: 
- If user says "add X to Y" → use "add_content" to preserve existing content
- If user says "replace Y with X" → use "replace_content" to overwrite
- Default to "add_content" unless explicitly replacing

Examples:
[
  {{"action_type": "edit_slide", "parameters": {{"slide_number": 3, "add_content": ["Agentic AI integration", "Advanced automation capabilities"]}}}},
  {{"action_type": "edit_slide", "parameters": {{"slide_number": 2, "new_title": "Updated Title", "replace_content": ["New bullet 1", "New bullet 2"]}}}},
  {{"action_type": "add_slide", "parameters": {{"title": "New Slide", "content": ["Bullet 1", "Bullet 2"], "position": 4}}}}
]

Return only valid JSON array.
"""

        try:
            actions_response = await openai_service.get_completion([
                {"role": "system", "content": "Convert plans to JSON actions. Return only valid JSON."},
                {"role": "user", "content": action_prompt}
            ])
            
            # Parse JSON response
            actions = json.loads(actions_response)
            return actions if isinstance(actions, list) else []
            
        except Exception as e:
            logger.warning(f"Could not parse actions: {e}")
            return []
    
    async def _execute_action(self, state: AgentState) -> AgentState:
        """Execute the next action in the plan"""
        
        if not state["actions"]:
            state["result"] = "No actions to execute"
            return state
        
        # Get next action
        action = state["actions"].pop(0)
        state["current_action"] = action
        
        logger.info(f"Agent: Executing {action['action_type']}")
        
        try:
            if action["action_type"] == "edit_slide":
                result = await self._edit_slide_tool(action["parameters"], state)
            elif action["action_type"] == "add_slide":
                result = await self._add_slide_tool(action["parameters"], state)
            elif action["action_type"] == "delete_slide":
                result = await self._delete_slide_tool(action["parameters"], state)
            elif action["action_type"] == "create_presentation":
                result = await self._create_presentation_tool(action["parameters"], state)
            else:
                result = f"Unknown action type: {action['action_type']}"
            
            state["messages"].append({
                "role": "system", 
                "content": f"Executed {action['action_type']}: {result}"
            })
            
        except Exception as e:
            error_msg = f"Error executing {action['action_type']}: {str(e)}"
            logger.error(error_msg)
            state["messages"].append({"role": "system", "content": error_msg})
        
        return state
    
    async def _reflect_on_result(self, state: AgentState) -> AgentState:
        """Reflect on the execution result and decide next steps"""
        
        if not state["actions"]:
            # No more actions, we're done
            state["result"] = "All actions completed successfully"
            return state
        
        # Check if we should continue or stop
        reflection_prompt = f"""
Review the execution so far and decide if we should continue.

Original Request: {state['user_request']}
Actions Completed: {len([msg for msg in state['messages'] if 'Executed' in msg.get('content', '')])}
Remaining Actions: {len(state['actions'])}

Should we continue executing the remaining actions?
Respond with 'continue' or 'stop' and a brief reason.
"""

        try:
            reflection = await openai_service.get_completion([
                {"role": "system", "content": "You are reflecting on presentation modification progress."},
                {"role": "user", "content": reflection_prompt}
            ])
            
            state["messages"].append({"role": "assistant", "content": f"Reflection: {reflection}"})
            
        except Exception as e:
            logger.warning(f"Reflection failed: {e}")
        
        return state
    
    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue executing actions"""
        return "continue" if state["actions"] else "end"
    
    async def _edit_slide_tool(self, params: Dict[str, Any], state: AgentState) -> str:
        """Tool: Edit an existing slide using MCP directly"""
        
        from app.services.mcp import mcp_client
        
        slide_number = params.get("slide_number", 1)
        new_title = params.get("new_title")
        add_content = params.get("add_content", [])
        replace_content = params.get("replace_content", [])
        
        # Ensure output file exists
        output_path = Path(state["output_path"])
        if not output_path.exists():
            import shutil
            shutil.copy2(state["presentation_path"], output_path)
            logger.info(f"Copied template to output path for editing")
        
        # Open the presentation
        await mcp_client.open_presentation(str(output_path))
        
        # Edit the slide using MCP's manage_text tool
        slide_index = slide_number - 1  # Convert to 0-based index
        
        if new_title:
            await mcp_client.manage_text(
                action="replace",
                slide_index=slide_index,
                text=new_title,
                placeholder_index=0  # Title placeholder
            )
        
        if replace_content:
            # Replace all content
            await mcp_client.manage_text(
                action="replace",
                slide_index=slide_index,
                text="\n".join(f"• {item}" for item in replace_content),
                placeholder_index=1  # Content placeholder
            )
        elif add_content:
            # Add to existing content
            slide_info = await mcp_client.get_slide_info(slide_index)
            existing_text = slide_info.get("content", "")
            new_text = existing_text + "\n" + "\n".join(f"• {item}" for item in add_content)
            await mcp_client.manage_text(
                action="replace",
                slide_index=slide_index,
                text=new_text,
                placeholder_index=1
            )
        
        # Save the presentation
        await mcp_client.save_presentation(str(output_path))
        
        return f"Successfully edited slide {slide_number}"
    
    async def _add_slide_tool(self, params: Dict[str, Any], state: AgentState) -> str:
        """Tool: Add a new slide using MCP directly"""
        
        from app.services.mcp import mcp_client
        import shutil
        
        title = params.get("title", "New Slide")
        content = params.get("content", [])
        position = params.get("position")
        
        # Ensure we have a presentation to work with
        output_path = Path(state["output_path"])
        if not output_path.exists():
            shutil.copy2(state["presentation_path"], output_path)
            logger.info(f"Copied template to output path for modification")
        
        # Open the presentation
        await mcp_client.open_presentation(str(output_path))
        
        # Use MCP's template system for intelligent slide creation
        templates = await mcp_client.list_slide_templates()
        
        # Find best template for content
        template_id = "title_and_content"  # Default
        if title and content:
            template_id = "title_and_content"
        elif title and not content:
            template_id = "title_only"
        
        # Create slide from template
        result = await mcp_client.create_slide_from_template(
            template_id=template_id,
            position=position,
            content={
                "title": title,
                "bullets": content
            }
        )
        
        # Save the presentation
        await mcp_client.save_presentation(str(output_path))
        
        return f"Successfully added slide: {title}"
    
    async def _delete_slide_tool(self, params: Dict[str, Any], state: AgentState) -> str:
        """Tool: Delete a slide using MCP directly"""
        
        from app.services.mcp import mcp_client
        import shutil
        
        slide_number = params.get("slide_number", 1)
        
        # Ensure output file exists
        output_path = Path(state["output_path"])
        if not output_path.exists():
            shutil.copy2(state["presentation_path"], output_path)
            logger.info(f"Copied template to output path for deletion")
        
        # Open the presentation
        await mcp_client.open_presentation(str(output_path))
        
        # Delete the slide (MCP uses 0-based indexing)
        slide_index = slide_number - 1
        
        # Note: MCP doesn't have a direct delete_slide tool, but we can achieve this
        # by recreating the presentation without that slide
        slides_info = await mcp_client.get_presentation_info()
        total_slides = slides_info.get("slide_count", 0)
        
        if slide_number < 1 or slide_number > total_slides:
            return f"Error: Invalid slide number {slide_number}"
        
        # For now, we'll use the manage_text to clear the slide
        # In a production system, you'd want to add a delete_slide tool to MCP
        await mcp_client.manage_text(
            action="delete",
            slide_index=slide_index,
            placeholder_index=0
        )
        await mcp_client.manage_text(
            action="delete",
            slide_index=slide_index,
            placeholder_index=1
        )
        
        # Save the presentation
        await mcp_client.save_presentation(str(output_path))
        
        return f"Successfully deleted content from slide {slide_number}"
    
    async def _create_presentation_tool(self, params: Dict[str, Any], state: AgentState) -> str:
        """Tool: Create a new presentation from template using MCP"""
        
        from app.services.mcp import mcp_client
        
        try:
            # Use MCP's auto-generation capability for intelligent creation
            topic = state["user_request"]
            template_path = state["presentation_path"]
            output_path = state["output_path"]
            
            # If we have a template, use it
            if Path(template_path).exists():
                await mcp_client.create_presentation(template_path=str(template_path))
            else:
                await mcp_client.create_presentation()
            
            # Use AI to generate content based on request
            slides_spec = params.get("slides_spec", [])
            if slides_spec:
                # If we have specific slides to create
                for slide in slides_spec:
                    await mcp_client.create_slide_from_template(
                        template_id="title_and_content",
                        content=slide
                    )
            else:
                # Use auto-generation for the topic
                result = await mcp_client.auto_generate_presentation(
                    topic=topic,
                    num_slides=5,
                    style="professional"
                )
            
            # Optimize the text for readability
            presentation_info = await mcp_client.get_presentation_info()
            for i in range(presentation_info.get("slide_count", 0)):
                await mcp_client.optimize_slide_text(slide_index=i)
            
            # Save the presentation
            await mcp_client.save_presentation(str(output_path))
            
            return f"Successfully created presentation with AI-powered content generation"
            
        except Exception as e:
            return f"Error creating presentation: {str(e)}"

# Create singleton instance
presentation_agent = PresentationAgent()
