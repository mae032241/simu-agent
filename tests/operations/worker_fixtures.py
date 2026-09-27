"""Attach exact synthetic workers through the production participation boundary."""
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.service.worker_connections import WorkerConnections


def attached_worker(runtime, root, name):
    run_id = runtime.scheduler_bindings.resolve(instance=root.facade.instance,
        namespace="run", name=name)
    value = runtime.runs.status(run_id)
    caller = ("source-test-session", "worker-" + run_id)
    WorkerConnections(runtime.runs).attach(run_id=run_id,
        platform_session=caller[0], thread_id=caller[1])
    return LocalWorkerMCPRouter(runtime.runs, operation_id=value.operation_id,
        operation_digest=value.operation_digest, run_id=run_id, trusted_caller=caller)
