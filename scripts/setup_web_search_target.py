"""Create, inspect, or tear down the private AgentCore Web Search target.

This script is intentionally explicit and guarded. It never changes the public
MCP API Gateway/Lambda path. ``apply`` and ``delete`` require ``--confirm-live``
and the exact approved personal account, profile, and ``us-east-1`` region.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any

import boto3


APPROVED_PERSONAL_ACCOUNT = "831597648506"
WEB_SEARCH_CONNECTOR_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:aws:tool/web-search.v1"
)
DEFAULT_GATEWAY_NAME = "CapeFearWebSearchGateway"
DEFAULT_TARGET_NAME = "web-search-tool"
DEFAULT_ROLE_NAME = "CapeFearWebSearchGatewayRole"
DEFAULT_CONNECTOR_VERSION = "1.1.0"
ROLE_POLICY_NAME = "CapeFearWebSearchOutbound"
N_CINO_PROFILE_MARKERS = ("ncino", "n-cino", "company", "work")


def _validate_args(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"\d{12}", args.account):
        raise SystemExit("--account must be a 12-digit AWS account ID")
    if args.account != APPROVED_PERSONAL_ACCOUNT:
        raise SystemExit(
            "refusing non-approved or nCino account; --account must be the approved personal account"
        )
    if any(marker in args.profile.lower() for marker in N_CINO_PROFILE_MARKERS):
        raise SystemExit("refusing nCino/company AWS profile; use the approved personal profile")
    if args.region != "us-east-1":
        raise SystemExit("AgentCore Web Search is restricted to --region us-east-1")
    if args.action in {"apply", "delete"} and not args.confirm_live:
        raise SystemExit(f"{args.action} requires --confirm-live after human AWS approval")


def _session(args: argparse.Namespace) -> boto3.Session:
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity.get("Account") != args.account:
        raise SystemExit("refusing AWS identity mismatch for the requested personal account")
    return session


def _role_documents(account: str, region: str, gateway_arn: str = "*") -> tuple[dict[str, Any], dict[str, Any]]:
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {"StringEquals": {"aws:SourceAccount": account}},
        }],
    }
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeOnlyThisGateway",
                "Effect": "Allow",
                "Action": "bedrock-agentcore:InvokeGateway",
                "Resource": gateway_arn if gateway_arn != "*" else f"arn:aws:bedrock-agentcore:{region}:{account}:gateway/*",
            },
            {
                "Sid": "InvokeManagedWebSearch",
                "Effect": "Allow",
                "Action": "bedrock-agentcore:InvokeWebSearch",
                "Resource": WEB_SEARCH_CONNECTOR_ARN,
            },
        ],
    }
    return trust, policy


def _ensure_role(iam: Any, args: argparse.Namespace) -> str:
    trust, policy = _role_documents(args.account, args.region)
    try:
        role = iam.get_role(RoleName=args.role_name)["Role"]
    except iam.exceptions.NoSuchEntityException:
        role = iam.create_role(
            RoleName=args.role_name,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Outbound role for Cape Fear's private AgentCore Web Search gateway.",
            Tags=[{"Key": "project", "Value": "CapeFearSurfGuide"}, {"Key": "purpose", "Value": "WebSearch"}],
        )["Role"]
    iam.put_role_policy(
        RoleName=args.role_name,
        PolicyName=ROLE_POLICY_NAME,
        PolicyDocument=json.dumps(policy),
    )
    return role["Arn"]


def _set_exact_gateway_policy(iam: Any, args: argparse.Namespace, gateway_arn: str) -> None:
    _, policy = _role_documents(args.account, args.region, gateway_arn)
    iam.put_role_policy(
        RoleName=args.role_name,
        PolicyName=ROLE_POLICY_NAME,
        PolicyDocument=json.dumps(policy),
    )


def _list_all(client: Any, operation: str, result_key: str, **kwargs: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        request = dict(kwargs)
        if token:
            request["nextToken"] = token
        response = getattr(client, operation)(**request)
        items.extend(response.get(result_key, []))
        token = response.get("nextToken")
        if not token:
            return items


def _gateway(control: Any, name: str) -> dict[str, Any] | None:
    return next((item for item in _list_all(control, "list_gateways", "items") if item.get("name") == name), None)


def _target(control: Any, gateway_id: str, name: str) -> dict[str, Any] | None:
    return next(
        (item for item in _list_all(control, "list_gateway_targets", "items", gatewayIdentifier=gateway_id)
         if item.get("name") == name),
        None,
    )


def _wait_gateway(control: Any, gateway_id: str, timeout_s: int = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        gateway = control.get_gateway(gatewayIdentifier=gateway_id)
        if gateway.get("status") == "READY":
            return gateway
        if gateway.get("status") in {"FAILED", "UPDATE_UNSUCCESSFUL"}:
            raise RuntimeError(f"gateway did not become ready: {gateway.get('statusReasons', [])}")
        if time.monotonic() >= deadline:
            raise TimeoutError("timed out waiting for AgentCore Gateway to become READY")
        time.sleep(2)


def _target_configuration(version: str) -> dict[str, Any]:
    return {
        "mcp": {
            "connector": {
                "source": {"connectorId": "web-search", "version": version},
                "configurations": [{"name": "WebSearch", "parameterValues": {}}],
            }
        }
    }


def apply(args: argparse.Namespace, session: boto3.Session) -> dict[str, Any]:
    control = session.client("bedrock-agentcore-control")
    iam = session.client("iam")
    role_arn = _ensure_role(iam, args)
    gateway = _gateway(control, args.gateway_name)
    if gateway is None:
        gateway = control.create_gateway(
            name=args.gateway_name,
            description="Private Cape Fear explanation-only Web Search Gateway.",
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="AWS_IAM",
        )
        gateway_id = gateway["gatewayId"]
        gateway = _wait_gateway(control, gateway_id)
    else:
        gateway_id = gateway["gatewayId"]
        gateway = control.get_gateway(gatewayIdentifier=gateway_id)
    _set_exact_gateway_policy(iam, args, gateway["gatewayArn"])

    target = _target(control, gateway_id, args.target_name)
    if target is None:
        target = control.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=args.target_name,
            description="AWS-native Web Search context; never a policy signal.",
            targetConfiguration=_target_configuration(args.connector_version),
            credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        )
    return {
        "account": args.account,
        "region": args.region,
        "gateway": {"id": gateway_id, "arn": gateway.get("gatewayArn"), "status": gateway.get("status")},
        "target": {"id": target.get("targetId"), "name": target.get("name"), "status": target.get("status")},
        "role_arn": role_arn,
        "connector_id": "web-search",
        "connector_version": args.connector_version,
    }


def describe(args: argparse.Namespace, session: boto3.Session) -> dict[str, Any]:
    control = session.client("bedrock-agentcore-control")
    gateway = _gateway(control, args.gateway_name)
    if gateway is None:
        return {"account": args.account, "region": args.region, "gateway": None}
    gateway_detail = control.get_gateway(gatewayIdentifier=gateway["gatewayId"])
    target = _target(control, gateway["gatewayId"], args.target_name)
    return {
        "account": args.account,
        "region": args.region,
        "gateway": {"id": gateway["gatewayId"], "arn": gateway_detail.get("gatewayArn"), "status": gateway_detail.get("status")},
        "target": None if target is None else {"id": target.get("targetId"), "name": target.get("name"), "status": target.get("status")},
    }


def delete(args: argparse.Namespace, session: boto3.Session) -> dict[str, Any]:
    control = session.client("bedrock-agentcore-control")
    iam = session.client("iam")
    gateway = _gateway(control, args.gateway_name)
    deleted: dict[str, Any] = {"target": False, "gateway": False, "role": False}
    if gateway is not None:
        gateway_id = gateway["gatewayId"]
        target = _target(control, gateway_id, args.target_name)
        if target is not None:
            control.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target["targetId"])
            deleted["target"] = True
        control.delete_gateway(gatewayIdentifier=gateway_id)
        deleted["gateway"] = True
    try:
        iam.delete_role_policy(RoleName=args.role_name, PolicyName=ROLE_POLICY_NAME)
        iam.delete_role(RoleName=args.role_name)
        deleted["role"] = True
    except iam.exceptions.NoSuchEntityException:
        pass
    return {"account": args.account, "region": args.region, "deleted": deleted}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("describe", "apply", "delete"), default="describe")
    parser.add_argument("--account", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--gateway-name", default=DEFAULT_GATEWAY_NAME)
    parser.add_argument("--target-name", default=DEFAULT_TARGET_NAME)
    parser.add_argument("--role-name", default=DEFAULT_ROLE_NAME)
    parser.add_argument("--connector-version", default=DEFAULT_CONNECTOR_VERSION)
    parser.add_argument("--confirm-live", action="store_true", help="confirm an approved AWS create/delete")
    args = parser.parse_args()
    _validate_args(args)
    session = _session(args)
    operation = {"describe": describe, "apply": apply, "delete": delete}[args.action]
    print(json.dumps(operation(args, session), indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
