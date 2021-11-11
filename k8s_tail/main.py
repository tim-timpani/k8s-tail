import argparse
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import re
import subprocess
import time
import yaml

KUBECTL_CMD = "kubectl"
DEF_DIRECTORY = os.getenv("LOG_DIRECTORY")
TIME_STAMP = datetime.strftime(datetime.now(), "%Y-%m-%d_%H-%M-%S.%f")
DEF_KUBECONFIG = os.getenv("KUBECONFIG", os.path.expanduser("~/.kube/config"))

logger = logging.getLogger("k8s_tail")


@dataclass
class ContainerSpec:

    namespace: str
    pod: str
    container: str

    @property
    def file_path(self):
        return f"{self.namespace}_{self.pod}_{self.container}.log"


def run_kubectl_bg(command_args: list[str], kubeconfig: str = DEF_KUBECONFIG,
                   backround_to_file: str = "/dev/null") -> subprocess.Popen:
    run_env = os.environ.copy()
    run_env["KUBECONFIG"] = kubeconfig
    cmd = [KUBECTL_CMD]
    cmd.extend(command_args)

    return subprocess.Popen(
        cmd,
        env=run_env,
        stdout=open(backround_to_file, "w")
    )


def run_kubectl(command_args: list[str], kubeconfig: str = DEF_KUBECONFIG) -> str:
    run_env = os.environ.copy()
    run_env["KUBECONFIG"] = kubeconfig
    cmd = [KUBECTL_CMD]
    cmd.extend(command_args)

    result = subprocess.run(
        cmd,
        env=run_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to run kubeclt args={command_args}"
                           f" rc={result.returncode} stderr={result.stderr.decode('utf-8')}")
    return result.stdout.decode('utf-8')


def get_containers(pod_regex: str, container_regex: str = ".",
                   namespace: str = "", kubeconfig: str = DEF_KUBECONFIG) -> list[ContainerSpec]:
    containers = []
    command_args = ["get", "pod", "-o", "yaml"]
    if namespace:
        command_args.extend(["-n", namespace])
    else:
        command_args.append("-A")
    re_pod = re.compile(pod_regex)
    re_container = re.compile(container_regex)
    pod_output = run_kubectl(command_args=command_args, kubeconfig=kubeconfig)
    pods = yaml.safe_load(pod_output)["items"]
    for pod in pods:
        if not re_pod.search(pod["metadata"]["name"]):
            continue
        for container in pod["spec"]["containers"]:
            if not re_container.search(container["name"]):
                continue
            containers.append(ContainerSpec(
                namespace=pod["metadata"]["namespace"],
                pod=pod["metadata"]["name"],
                container=container["name"]
            ))
    return containers


def tail_logs(log_dir: str, containers: list[ContainerSpec], kubeconfig: str = DEF_KUBECONFIG):
    procs: list[subprocess.Popen] = []
    for container in containers:
        log_file = os.path.join(log_dir, container.file_path)
        logger.info(f"Starting tail for log {container.file_path}")
        cmd = ["logs", "-f", container.pod, "-c", container.container, "-n", container.namespace]
        proc = run_kubectl_bg(command_args=cmd, kubeconfig=kubeconfig, backround_to_file=log_file)
        procs.append(proc)
    ans = "N"
    while ans.lower() != "stop":
        ans = input("Log tails running. Enter stop when finished")
    for proc in procs:
        proc.kill()


def main():
    parser = argparse.ArgumentParser(description="Tail container logs")
    parser.add_argument(
        "--logdir", "-l",
        default=DEF_DIRECTORY,
        help=f"Path to main directory to create log subdirectory, default={DEF_DIRECTORY}"
    )
    parser.add_argument(
        "--kubeconfig", "-k",
        default=DEF_KUBECONFIG,
        help=f"Path to kubeconfig. default={DEF_KUBECONFIG}"
    )
    parser.add_argument(
        "--namespace", "-n",
        default="",
        help="Pod namespace. defaults to all namespace"
    )
    parser.add_argument(
        "--pod", "-p",
        default=".",
        help="Regex string to match pod name. defaults to all pods"
    )
    parser.add_argument(
        "--container", "-c",
        default=".",
        help=f"Regex string to match container name. defaults to all containers"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()
    if args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)

    kubeconfig = os.path.expanduser(args.kubeconfig)
    logger.info(f"Using kubeconfig at {kubeconfig}")

    logger.info("Getting containers")
    containers = get_containers(
        pod_regex=args.pod,
        container_regex=args.container,
        namespace=args.namespace,
        kubeconfig=kubeconfig
    )
    if len(containers) < 1:
        logger.error("No containers found matching criterea")
        return
    logger.info(f"Found {len(containers)} containers matching criterea")

    log_dir = os.path.join(os.path.expanduser(args.logdir), TIME_STAMP)
    os.mkdir(log_dir)
    logging.info(f"Tailing logs into directory {log_dir}")

    tail_logs(
        log_dir=log_dir,
        containers=containers,
        kubeconfig=kubeconfig
    )


if __name__ == "__main__":
    main()
