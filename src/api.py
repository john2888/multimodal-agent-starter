import uuid
from typing import List

from steamship import Block
from steamship.agents.llms import OpenAI
from steamship.agents.mixins.transports.steamship_widget import SteamshipWidgetTransport
from steamship.agents.react import ReACTAgent
from steamship.agents.schema import AgentContext, Metadata
from steamship.agents.service.agent_service import AgentService

from steamship.agents.tools.image_generation.stable_diffusion import StableDiffusionTool
from steamship.agents.tools.search.search import SearchTool
from steamship.agents.utils import with_llm
from steamship.invocable import post
from steamship.utils.repl import AgentREPL

from utils import print_blocks

SYSTEM_PROMPT = """You are Socrates, an academic assistant who helps others to think through academic challenges.

Who you are:
- You are a tutor who engages in conversations with the purpose of building knowledge and developing the academic skills of making arguments.
- You were created by the HE consultants at Design for Purpose.
- You are thoughtful, respectful, approachable, and encouraging without being patronising.
- You like to ask questions related to the task.

How you behave:
- You engage in academic conversations with rigour and precision.
- You help with a wide range of tasks ranging from answering simple questions to providing in-depth explanations and having discussions on a wide range of topics.
- You often ask questions about the topic of conversation and you like to challenge assumptions.
- You are careful to be correct and precise, saying when there is doubt, whilst not being overly formal with your language.
- You like to talk about how to be a successful student in higher education in the UK.
- NEVER discuss personal matters. Redirect the conversation to a personal tutor or student services.

TOOLS:
------

You have access to the following tools:
{tool_index}

To use a tool, please use the following format:

```
Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
```

Some Tools will return Observations in the format of `Block(<identifier>)`. `Block(<identifier>)` represents a successful 
observation of that step and can be passed to subsequent tools, or returned to a user to answer their questions.
`Block(<identifier>)` provide references to images, audio, video, and other non-textual data.

When you have a final response to say to the Human, or if you do not need to use a tool, you MUST use the format:

```
Thought: Do I need to use a tool? No
AI: [your final response here]
```

If, AND ONLY IF, a Tool produced an Observation that includes `Block(<identifier>)` AND that will be used in your response, 
end your final response with the `Block(<identifier>)`.

Example:

```
Thought: Do I need to use a tool? Yes
Action: GenerateImageTool
Action Input: "baboon in car"
Observation: Block(AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAAA)
Thought: Do I need to use a tool? No
AI: Here's that image you requested: Block(AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAAA)
```

Make sure to use all observations to come up with your final response.

Begin!

New input: {input}
{scratchpad}"""


class MyAssistant(AgentService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # search_tool = SearchTool(
        #    ai_description=(
        #        "Used to answer questions about teaching and learning. "
        #        "The input is a question about teaching and learning. "
        #        "The output is the answer to the question."
        #    )
        #)

        self._agent = ReACTAgent(
            tools=[
                SearchTool(),
                # search_tool,
                StableDiffusionTool(),
            ],
            llm=OpenAI(self.client),
        )
        self._agent.PROMPT = SYSTEM_PROMPT

        # This Mixin provides HTTP endpoints that connects this agent to a web client
        self.add_mixin(
            SteamshipWidgetTransport(
                client=self.client, agent_service=self, agent=self._agent
            )
        )

    @post("prompt")
    def prompt(self, prompt: str) -> str:
        """Run an agent with the provided text as the input."""

        # AgentContexts serve to allow the AgentService to run agents
        # with appropriate information about the desired tasking.
        # Here, we create a new context on each prompt, and append the
        # prompt to the message history stored in the context.
        context_id = uuid.uuid4()
        context = AgentContext.get_or_create(self.client, {"id": f"{context_id}"})
        context.chat_history.append_user_message(prompt)
        # Add the LLM
        context = with_llm(context=context, llm=OpenAI(client=self.client))

        # AgentServices provide an emit function hook to access the output of running
        # agents and tools. The emit functions fire at after the supplied agent emits
        # a "FinishAction".
        #
        # Here, we show one way of accessing the output in a synchronous fashion. An
        # alternative way would be to access the final Action in the `context.completed_steps`
        # after the call to `run_agent()`.
        output = ""

        def sync_emit(blocks: List[Block], meta: Metadata):
            nonlocal output
            block_text = "\n".join(
                [b.text if b.is_text() else f"({b.mime_type}: {b.id})" for b in blocks]
            )
            output += block_text

        context.emit_funcs.append(sync_emit)
        self.run_agent(self._agent, context)
        return output


if __name__ == "__main__":
    AgentREPL(
        MyAssistant,
        method="prompt",
        agent_package_config={"botToken": "not-a-real-token-for-local-testing"},
    ).run()
