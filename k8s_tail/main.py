import argparse
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import re
import subprocess
import tempfile
import yaml

KUBECTL_CMD = "kubectl"
LOG_VIEWER = os.getenv("LOG_VIEWER", "lnav")
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
        """Filename used for saving logs"""
        return f"{self.namespace}_{self.pod}_{self.container}.log"


class SearchSpec:
    """Class to handle search parameters and search methods for container selection"""

    def __init__(self, namespaces: (None, list) = None, pods: (None, list) = None, containers: (None, list) = None):
        self.namespaces = namespaces or []
        pod_regex_strings = pods or []
        self.pod_regexes = [re.compile(p) for p in pod_regex_strings]
        container_regex_strings = containers or []
        self.container_regexes = [re.compile(c) for c in container_regex_strings]

    def match(self, spec: ContainerSpec) -> bool:
        """
        Performs match against a Kubernetes container
        :param spec: ContainerSpec object describing the Kubernetes container
        :return: bool
        """

        if spec.namespace not in self.namespaces:
            return False

        # Check if pod matches only if we have pod regexes to match against
        if self.pod_regexes:
            for regex in self.pod_regexes:
                if regex.search(spec.pod):
                    break
            else:
                return False

        # If no container regexes, then just return True
        if not self.container_regexes:
            return True

        # Check through the container regexes
        for re_container in self.container_regexes:
            if re_container.search(spec.container):
                return True

        return False


def run_kubectl_bg(command_args: list[str], kubeconfig: str = DEF_KUBECONFIG,
                   backround_to_file: str = "/dev/null") -> subprocess.Popen:
    """
    Runs kubectl command in the background
    :param command_args: list of args to pass to kubectl
    :param kubeconfig: path to kubeconfig file
    :param backround_to_file: path to write output from command (defaults to /dev/null)
    :return: Popen object of the background command
    """
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
    """
    Runs kubectl command, waits for it to finish and returns stdout. Nonzero return code will
    raise a RuntimeError.
    :param command_args: list of args to pass to kubectl
    :param kubeconfig: path to kubeconfig file
    :return: string containing stdout
    """
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


def get_containers(search_spec: SearchSpec, kubeconfig: str = DEF_KUBECONFIG) -> list[ContainerSpec]:
    """
    Retrieve Kubernetes containers matching the desired search specification
    :param search_spec: SearchSpec object
    :param kubeconfig: path to kubeconfig file
    :return: list of ContainerSpec objects
    """
    containers = []
    command_args = ["get", "pod", "-A", "-o", "yaml"]
    pod_output = run_kubectl(command_args=command_args, kubeconfig=kubeconfig)
    pods = yaml.safe_load(pod_output)["items"]
    for pod in pods:
        for container in pod["spec"]["containers"]:
            container_spec = ContainerSpec(
                namespace=pod["metadata"]["namespace"],
                pod=pod["metadata"]["name"],
                container=container["name"]
            )
            if search_spec.match(container_spec):
                containers.append(container_spec)
    return containers


def tail_logs(log_dir: str, containers: list[ContainerSpec],
              args: argparse.Namespace, kubeconfig: str = DEF_KUBECONFIG):
    """
    Tail all the container logs.
    Uses subprocess.Popen to run several tail commands in the background. If viewing the logs, the tail procs
    will be killed once the user quits the viewer. Otherwise, the user must enter "stop" to stop the tail procs
    :param log_dir: Path to where the log files will be written
    :param containers: List of ContainerSpec objects
    :param args: argparse namespace (command line options).
    :param kubeconfig: Path to kubeconfig file
    :return:
    """

    optional_args = []
    if args.since:
        optional_args.extend(["--since", args.since])
    if args.tail:
        optional_args.extend(["--tail", args.tail])

    procs: list[subprocess.Popen] = []
    for container in containers:
        log_file = os.path.join(log_dir, container.file_path)
        logger.info(f"Starting tail for log {container.file_path}")
        cmd = ["logs", "-f", container.pod, "-c", container.container, "-n", container.namespace] + optional_args
        proc = run_kubectl_bg(command_args=cmd, kubeconfig=kubeconfig, backround_to_file=log_file)
        procs.append(proc)

    if args.view:
        os.system(f"{LOG_VIEWER} {log_dir}")
    else:
        ans = "N"
        while ans.lower() != "stop":
            ans = input("Log tails running. Enter stop when finished: ")

    # Kill all the tailing procs
    logger.info("Stopping log capture processes")
    for proc in procs:
        proc.kill()


def main():
    """Main logic function"""
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
        nargs="*",
        default=[],
        help="Pod namespace(s). defaults to all namespaces"
    )
    parser.add_argument(
        "--pod", "-p",
        nargs="*",
        default=[],
        help="Regex string(s) to match pod name. defaults to all pods"
    )
    parser.add_argument(
        "--container", "-c",
        nargs="*",
        default=[],
        help=f"Regex string(s) to match container name. defaults to all containers"
    )
    parser.add_argument(
        "--since", "-S",
        required=False,
        help=f"Logs newer than a relative duration like 5s, 2m, or 3h. Defaults to all logs"
    )
    parser.add_argument(
        "--tail", "-T",
        required=False,
        help=f"Lines of recent log file to display"
    )
    parser.add_argument(
        "--view", "-v",
        action="store_true",
        help=f"View the logs using '{LOG_VIEWER}' (override with env var LOG_VIEWER)"
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
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    kubeconfig = os.path.expanduser(args.kubeconfig)
    logger.info(f"Using kubeconfig at {kubeconfig}")

    #
    # Create a search spec based on command line args
    search_spec = SearchSpec(
        namespaces=args.namespace,
        pods=args.pod,
        containers=args.container
    )

    #
    # Get all matching containers
    logger.info("Getting containers")
    containers = get_containers(
        search_spec=search_spec,
        kubeconfig=kubeconfig
    )
    if len(containers) < 1:
        logger.error("No containers found matching criterea")
        return
    logger.info(f"Found {len(containers)} containers matching criterea")

    if args.logdir == "-":
        temp_dir = tempfile.TemporaryDirectory()
        log_dir = temp_dir.name
        args.view = True  # Force view to true, otherwise we accomplish nothing if it's false
        logger.info(f"Tailing logs into temp directory {log_dir}")
    else:
        temp_dir = None
        log_dir = os.path.join(os.path.expanduser(args.logdir), TIME_STAMP)
        os.mkdir(log_dir)
        logger.info(f"Tailing logs into directory {log_dir}")

    try:
        tail_logs(
            log_dir=log_dir,
            containers=containers,
            args=args,
            kubeconfig=kubeconfig
        )
    finally:
        if temp_dir is not None:
            logger.info(f"Cleaning up temp directory {temp_dir.name}")
            temp_dir.cleanup()
        else:
            logger.info(f"Logs retained in directory {log_dir}")


if __name__ == "__main__":
    main()
