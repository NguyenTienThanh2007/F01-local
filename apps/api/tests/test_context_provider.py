import asyncio,json
import httpx,pytest
from pydantic import ValidationError
from f01.config import Settings
from f01.domain.planning import ProjectPlan
from f01.domain.context_planning import ContextPlan
from f01.providers.openai import OpenAIPlanningProvider
from f01.providers.base import ProviderError,ProviderErrorCode

def output(plan:ProjectPlan) -> dict[str,object]:
    content=ContextPlan(plan=plan,scope=['Proposed scope'],assumptions=['No source exists'],acceptance_criteria=['Review scope'],out_of_scope=['Deployment'])
    return {'status':'completed','output':[{'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':content.model_dump_json()}]}]}

def test_context_adapter_strict_schema_budget_no_tools_and_usage(settings:Settings,project_plan:ProjectPlan) -> None:
    calls=[]
    async def handler(request:httpx.Request) -> httpx.Response:
        body=json.loads(request.content);calls.append(body);assert body['max_output_tokens']==700;assert body['store'] is False;assert 'tools' not in body
        assert body['text']['format']['strict'] is True;assert body['input']=='authorized JSON context';assert 'OpenAI' not in str(ContextPlan.model_json_schema())
        return httpx.Response(200,json={**output(project_plan),'usage':{'input_tokens':12,'output_tokens':34}})
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider=OpenAIPlanningProvider(client=client,api_key=settings.openai_api_key,model=settings.openai_model,timeout_seconds=1)
            result=await provider.create_context_plan('authorized JSON context',700);assert result.input_tokens==12 and result.output_tokens==34
    asyncio.run(run());assert len(calls)==1

@pytest.mark.parametrize('status,body,code',[(429,{'error':{'code':'insufficient_quota'}},ProviderErrorCode.QUOTA),(401,{},ProviderErrorCode.AUTHENTICATION),(503,{},ProviderErrorCode.UNAVAILABLE),(200,{'status':'incomplete','output':[]},ProviderErrorCode.INCOMPLETE_RESPONSE),(200,{'status':'completed','output':[]},ProviderErrorCode.INVALID_RESPONSE)])
def test_context_provider_failures_are_sanitized_without_retry(settings:Settings,status:int,body:dict[str,object],code:ProviderErrorCode) -> None:
    calls=0
    async def handler(request:httpx.Request) -> httpx.Response:
        nonlocal calls;calls+=1;return httpx.Response(status,json={**body,'diagnostic':'synthetic-private-diagnostic'})
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider=OpenAIPlanningProvider(client=client,api_key=settings.openai_api_key,model=settings.openai_model,timeout_seconds=1)
            with pytest.raises(ProviderError) as failure:await provider.create_context_plan('{}',3000)
            assert failure.value.code==code;assert 'diagnostic' not in str(failure.value)
    asyncio.run(run());assert calls==1

def test_context_schema_rejects_tool_calls_and_execution_fields(project_plan:ProjectPlan) -> None:
    value={'plan':project_plan.model_dump(),'scope':['Proposed'],'assumptions':[],'acceptance_criteria':['Review'],'out_of_scope':[],'tool_calls':[{'name':'execute'}]}
    with pytest.raises(ValidationError):ContextPlan.model_validate(value)

def test_context_output_and_response_size_limits(settings:Settings,project_plan:ProjectPlan) -> None:
    async def run() -> None:
        for response in ({**output(project_plan),'usage':{'output_tokens':10000}}, {'status':'completed','output':[{'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':json.dumps({'invalid':'x'*270000})}]}]}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=response))) as client:
                provider=OpenAIPlanningProvider(client=client,api_key=settings.openai_api_key,model=settings.openai_model,timeout_seconds=1)
                with pytest.raises(ProviderError,match='PROVIDER_INVALID_RESPONSE'):await provider.create_context_plan('{}',3000)
    asyncio.run(run())

def test_context_credential_echo_and_timeout_are_rejected(settings:Settings,project_plan:ProjectPlan) -> None:
    assert settings.openai_api_key
    leaked=project_plan.model_copy(update={'product_summary':settings.openai_api_key.get_secret_value()})
    async def run() -> None:
        for slow in (False,True):
            async def handler(request:httpx.Request) -> httpx.Response:
                if slow:await asyncio.sleep(.03)
                return httpx.Response(200,json=output(leaked))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                provider=OpenAIPlanningProvider(client=client,api_key=settings.openai_api_key,model=settings.openai_model,timeout_seconds=.01)
                with pytest.raises(ProviderError) as failure:await provider.create_context_plan('{}',3000)
                assert failure.value.code==(ProviderErrorCode.TIMEOUT if slow else ProviderErrorCode.INVALID_RESPONSE)
    asyncio.run(run())
