from pathlib import Path


def test_live_agent_runtime_uses_the_http_contract_and_immutable_s3_code_artifact():
    template = (Path(__file__).resolve().parents[1] / "infra" / "agentcore-live-agent" / "runtime.yaml").read_text()
    assert "ProtocolConfiguration: HTTP" in template
    assert "CodeConfiguration:" in template
    assert "ArtifactBucketName" in template
    assert "ArtifactObjectVersion" in template
    assert "Runtime: PYTHON_3_11" in template
    assert "EntryPoint: [agentcore_live_entrypoint.py]" in template
    assert "ContainerImageUri" not in template
    assert "ContainerConfiguration" not in template
    assert "bedrock:InvokeModel" in template
    assert "NetworkMode: PUBLIC" in template
    assert "IdleRuntimeSessionTimeout: 60" in template
