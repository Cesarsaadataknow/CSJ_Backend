from typing import Optional, Literal
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langgraph.graph import StateGraph, START, MessagesState
from langchain_core.runnables import RunnableConfig
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import  ToolNode

from core.ai_services import AIServices
from inference.prompts import SYSTEM_PROMPT, PROMPTS_TOOLS, PROMPT_SEARCH_TOOL_BOOL, PROMPT_MRKDOWN_INSTRUCTION
from inference.tools import search_tool, retrieval_tool

ai_services = AIServices()
cosmos_db = ai_services.CosmosDBClient()

######################################################
# Chat State
######################################################
class ChatState(MessagesState):
    pdf_text: Optional[str] = None
    thread_id: Optional[str] = None


template_with_tools = ChatPromptTemplate([
    ("system", SYSTEM_PROMPT),
    ("placeholder", "{conversation}")
])

template_without_tools = ChatPromptTemplate([
    ("human", SYSTEM_PROMPT),
    ("placeholder", "{conversation}")
])

llm_gpt4_o = AIServices().AzureOpenAI(config={"model_name": 'gpt-4o'}).model_ai
llm_o1 = AIServices().AzureOpenAI(config={"model_name": "o1", "reasoning_effort": "low", "max_completion_tokens":20000}).model_ai
llm_o1_mini = AIServices().AzureOpenAI(config={"model_name": "o1-mini", "max_completion_tokens":20000}).model_ai

models = {
    'gpt-4o': {"model":llm_gpt4_o, "enabled_tools":True},
    "o1":{"model":llm_o1, "enabled_tools":True},
    "o1-mini":{"model":llm_o1_mini, "enabled_tools":False}
}

default_tools = {
    "search_tool": search_tool,
    "retrieval_tool": retrieval_tool
}

######################################################
# 3) Construir el Graph + checkpoint
######################################################
class PDFChatAgent:
    def __init__(self):

        workflow = StateGraph(state_schema=ChatState)
        
        workflow.add_node("AgentNode", self.agent_node)

        workflow.add_node("ToolsNode", ToolNode([search_tool, retrieval_tool]))
        
        # 3) Edge: START -> AgentNode
        workflow.add_edge(START, "AgentNode")
        workflow.add_conditional_edges("AgentNode", self.route_after_agent)
        workflow.add_edge("ToolsNode", "AgentNode")
        
        # 4) Saver con Cosmos
        self.cosmos_saver = ManualCosmosSaver(cosmos_db)

        # 5) Compilar
        self.app = workflow.compile() 

        # (Opcional) Generar imagen del grafo
        # image_data = self.app.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)
        # image = Image(image_data)
        # with open("graph_image.png", "wb") as f:
        #     f.write(image.data)
    
    # ######################################################
    # 2) agent_node (asíncrono) + tools usage
    ########################################################

    async def agent_node(
            self,
            state: ChatState,
            config: Optional[RunnableConfig] = None
        ) -> ChatState:
        """
        1) Inyecta system prompt y PDF
        2) Llama repetidamente al LLM (con .bind_tools([...]))
        Si el LLM produce tool_calls (ej: name="search_tool"), se ejecutan
        y se añade un AIMessage con los resultados. 
        Se repite hasta que no haya más tool_calls.
        3) Devuelve el estado final
        """
        # Preparar la conversacion

        max_messages = 15
        # Configuración del modelo y herramientas
        llm_raw_config = models[config["configurable"].get("model_name")] if config["configurable"].get("model_name") else models["gpt-4o"]
        llm_raw = llm_raw_config["model"]
        model_name_configured = config['configurable'].get('model_name') if config['configurable'].get('model_name') else 'gpt-4o'  
        print(f"\033[32mModelo configurado: {model_name_configured}\033[0m")

        if llm_raw_config["enabled_tools"]: # El modelo acepta Tool Calls

            tools = [default_tools[tool_name] for tool_name in config["configurable"].get("tools",["retrieval_tool","search_tool"])]

            llm_with_tools = llm_raw.bind_tools(tools)
            prompts_tools = [PROMPTS_TOOLS[tool_name] for tool_name in config["configurable"].get("tools",["retrieval_tool","search_tool"])]
            fprompts_tools = "\n".join(prompts_tools)
            conversation = state["messages"][-max_messages:]
            new_messages = template_with_tools.invoke(
                input = {
                    "fecha_hora": f"{datetime.now().isoformat()}",
                    "files":f"{state['pdf_text']}",
                    "cantidad_herramientas": f"{len(prompts_tools)}",
                    "prompts_tools": fprompts_tools,
                    "conversation":conversation,
                    "search_guide": PROMPT_SEARCH_TOOL_BOOL if config["configurable"].get("search_tool") else "",
                    "mrkdown_instruction": PROMPT_MRKDOWN_INSTRUCTION if model_name_configured in ["o1","o1-mini"] else ""
                }
            ).messages
        else: # El modelo no acepta Tool Calls
            tools = []
            llm_with_tools = llm_raw
            prompts_tools = []
            fprompts_tools = ""
            conversation_without_tools_and_system_messages = []

            for msg in state["messages"][-max_messages:]:
                if isinstance(msg, SystemMessage):
                    h_msg = HumanMessage(content=msg.content)
                    conversation_without_tools_and_system_messages.append(h_msg)
                    print("\033[92m" + "System to Human Message" + "\033[0m")
                elif isinstance(msg, ToolMessage):
                    ai_msg = AIMessage(content=msg.content)
                    conversation_without_tools_and_system_messages.append(ai_msg)
                else:
                    conversation_without_tools_and_system_messages.append(msg)
                    
            conversation = conversation_without_tools_and_system_messages
            new_messages = template_without_tools.invoke(
                input = {
                    "fecha_hora": f"{datetime.now().isoformat()}",
                    "files":f"{state['pdf_text']}",
                    "cantidad_herramientas": f"{len(prompts_tools)}",
                    "prompts_tools": fprompts_tools,
                    "conversation":conversation,
                    "search_guide": PROMPT_SEARCH_TOOL_BOOL if config["configurable"].get("search_tool") else "",
                    "mrkdown_instruction": PROMPT_MRKDOWN_INSTRUCTION if model_name_configured in ["o1","o1-mini"] else ""
                
                }
            ).messages
        response_msg = llm_with_tools.invoke(new_messages)
        tool_calls_verified = []
        if response_msg.tool_calls:
            for tool_call in response_msg.tool_calls:

                if tool_call["name"] == "retrieval_tool":
                    print(f"\033[32m Tool Call: {tool_call['name']}  conversation_id {state['thread_id']}\033[0m")

                    arguments = tool_call["args"]
                    arguments["conversation_id"] = state["thread_id"]
                    tool_call["args"] = arguments
                    tool_calls_verified.append(tool_call)
                else:
                    tool_calls_verified.append(tool_call)

                response_msg.tool_calls = tool_calls_verified 
        
        print(f"\033[32m {response_msg.usage_metadata} \033[0m")
        new_messages.append(response_msg)

        return {
            "messages": new_messages,
            "pdf_text": state["pdf_text"],
            "thread_id": state["thread_id"]
        }

    def route_after_agent(
            self,
            state: ChatState,
        ) -> Literal["AgentNode","ToolsNode", "__end__"]:
        """
            This function determines the next step in a chat flow based on the last message received. It checks if the last message is an AIMessage and if it contains any tool calls. If not an AIMessage, it returns "AgentNode". If there are tool calls, it returns "ToolsNode". Otherwise, it returns "__end__".
        """
        last_message = state["messages"][-1]

        # "If for some reason the last message is not an AIMessage (due to a bug or unexpected behavior elsewhere in the code),
        # it ensures the system doesn't crash but instead tries to recover by calling the agent model again.
        if not isinstance(last_message, AIMessage):
            return "AgentNode"


        if last_message.tool_calls:
            return "ToolsNode"

        else:
            return "__end__"
    
    async def invoke_flow(
        self,
        user_input: str,  
        message_id: str,
        conversation_id: str,
        conversation_name: str,
        user_id: str,
        pdf_text: Optional[list[str]] = {},
        extra_params: Optional[dict] = {}
        ) -> tuple[ChatState, dict]:  
        
        # 1. Recuperar historial previo
        history_messages , all_hist_files = await self.cosmos_saver.get_conversation_history(
            conversation_id, user_id
        )

        all_files_list = all_hist_files + pdf_text if (pdf_text and all_hist_files) else all_hist_files if all_hist_files else pdf_text if pdf_text else None
        
        files_before_loaded = str(all_hist_files) if all_hist_files else 'ninguno'
        
        if pdf_text:
            text_about_files = "Archivos recién cargados: "+ ", ".join(pdf_text) + "  \nArchivos cargados antes:" + files_before_loaded
        
        elif all_hist_files:
            text_about_files = "\nArchivos cargados antes:" + files_before_loaded
        
        else:
            text_about_files = None

        # 2. Construir lista de mensajes completa
        new_human_message = HumanMessage(
            content=user_input,
            id=message_id,
            response_metadata={"timestamp": datetime.now().isoformat()}
        )
        all_messages = history_messages + [new_human_message]
        
        # 3. Ejecutar el flujo
        new_state = await self.app.ainvoke(
            {"messages": all_messages, "pdf_text": text_about_files,"thread_id": conversation_id},
            config={
                "configurable": {
                    "thread_id": conversation_id,
                    "user_id": user_id,
                    "model_name":extra_params.get("model_name"),
                    "search_tool":extra_params.get("search_tool"),
                    }}
        )

        # 4. Extraer y guardar solo el último intercambio
        new_messages = new_state["messages"][len(all_messages):]
        new_ai_messages = [msg for msg in new_messages if isinstance(msg, AIMessage)]
        if not new_ai_messages:
            raise ValueError("No se generó respuesta de AI")
        ai_response = new_ai_messages[-1]
        

        doc = await self.cosmos_saver.save_conversation(
            user_message=new_human_message,
            ai_message=ai_response,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            message_id=message_id,
            user_id=user_id,
            files_in_conversation=all_files_list,
            files_in_message=pdf_text,
            extra_params=extra_params
        )

        if doc.get('rate') == 2:    
            # if "message" in new_state and new_state["message"]:
            # Actualizamos el contenido del último mensaje
            new_state["messages"][-1].content = "Mensaje cancelado por el usuario"
                
        return new_state, doc

class ManualCosmosSaver:
    def __init__(self, cosmos_client):
        self.cosmos_client = cosmos_client

    def _message_to_dict(self, message: BaseMessage) -> dict:
        return {
            "content": message.content,
            "additional_kwargs": getattr(message, "additional_kwargs", {}),
            "response_metadata": getattr(message, "response_metadata", {}),
            "id": getattr(message, "id", ""),
            "created_at": datetime.now().isoformat()
        }

    async def save_conversation(
        self, 
        user_message: BaseMessage, 
        ai_message: BaseMessage, 
        message_id: str, 
        conversation_id: str, 
        conversation_name: str, 
        user_id: str,
        files_in_conversation: Optional[list[str]] = None,
        files_in_message: Optional[list[str]] = None,
        extra_params: Optional[dict] = {}
    ) -> dict:
        now = datetime.now().isoformat()

        # Intentamos leer el documento para conservar 'created_at' en caso de existir
        try:
            existing_doc = await self.cosmos_client.container_message_pairs.read_item(
                item=message_id, 
                partition_key=conversation_id
            )
            created_at = existing_doc.get("created_at", now)
        except CosmosResourceNotFoundError:
            created_at = now

        # Preparamos el documento base, preservando 'created_at' si ya existe
        doc = {
            "id": message_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "conversation_name": conversation_name,
            "files_in_message": files_in_message if files_in_message else None,
            "pdf_text": files_in_conversation if files_in_conversation else None,
            "created_at": created_at,
            "updated_at": now,
            "user_message": self._message_to_dict(user_message),
            "ai_message": self._message_to_dict(ai_message),
        }
        if extra_params and extra_params.get("flag_modifier"):
            doc["flag_modifier"] = True

        result = await self.cosmos_client.container_message_pairs.upsert_item(doc)
        return result

        

    async def get_conversation_history(self, conversation_id: str, user_id: str, max_messages: int = 20) -> tuple[list[BaseMessage], Optional[list[str]]]:
        query = (
            f"SELECT * FROM c WHERE c.conversation_id = '{conversation_id}' "
            f"AND c.user_id = '{user_id}' ORDER BY c.created_at DESC OFFSET 0 LIMIT {max_messages}"
        )
        docs = await self.cosmos_client.query_documents(query)
        
        history = []
        cutoff_time = None  # Aquí almacenaremos el 'updated_at' del documento con flag_modifier == True
        
        # Recorremos los documentos en orden cronológico (de más antiguo a más reciente)
        for doc in reversed(docs):
            # Obtenemos la fecha de creación del mensaje del usuario
            user_created_at = doc["user_message"].get("created_at")
            if user_created_at:
                msg_time = datetime.fromisoformat(user_created_at)
            else:
                # Si no hay fecha, asignamos un valor muy bajo para que se procese
                msg_time = datetime.min

            # Si ya se encontró un documento con flag_modifier == True,
            # se omiten los documentos cuyos mensajes tengan fecha de creación
            # anterior a la fecha de actualización del documento marcado.
            if cutoff_time is not None and msg_time < cutoff_time:
                continue

            # Agregamos el mensaje del usuario
            history.append(HumanMessage(
                content=doc["user_message"]["content"],
                additional_kwargs=doc["user_message"]["additional_kwargs"],
                response_metadata=doc["user_message"].get("response_metadata", {}),
                id=doc["user_message"]["id"]
            ))

            # Definimos el contenido del mensaje de la IA (aplicando la condición de rate)
            if doc.get("rate") == 2:
                ai_content = "Mensaje cancelado por el usuario"
            else:
                ai_content = doc["ai_message"]["content"]

            # Agregamos el mensaje de la IA
            history.append(AIMessage(
                content=ai_content,
                additional_kwargs=doc["ai_message"]["additional_kwargs"],
                response_metadata=doc["ai_message"].get("response_metadata", {}),
                id=doc["ai_message"]["id"]
            ))

            # Si este documento tiene flag_modifier == True y aún no se ha establecido cutoff_time,
            # se asigna el valor de updated_at (convertido a datetime)
            if doc.get("flag_modifier") is True and cutoff_time is None:
                updated_at_str = doc.get("updated_at")
                if updated_at_str:
                    cutoff_time = datetime.fromisoformat(updated_at_str)
        
        # Ultima lista de documentos cargados
        hist_files = next(
            (doc["pdf_text"] for doc in docs if doc.get("pdf_text")),
            None
        )

        return history, hist_files
