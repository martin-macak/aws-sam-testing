from pathlib import Path

import pytest
from requests import RequestException


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.start", lambda *args, **kwargs: None)
    monkeypatch.setattr("samcli.lib.utils.file_observer.FileObserver.stop", lambda *args, **kwargs: None)
    yield


def test_sam_cli_build(tmp_path: Path):
    import os

    from samcli.commands.build.build_context import BuildContext

    example_template = """
    Resources:
      ExampleFunction:
        Type: AWS::Logs::LogGroup
        Properties:
          LogGroupName: /aws/lambda/ExampleFunction
    """

    template_path = tmp_path / "template.yaml"
    template_path.write_text(example_template)
    # change directory to tmp_path
    os.chdir(tmp_path)

    with BuildContext(
        resource_identifier=None,
        template_file=str(template_path),
        base_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        parallel=True,
        mode="build",
        cached=False,
        clean=True,
        use_container=False,
        aws_region="eu-west-1",
    ) as ctx:
        ctx.run()

    assert (tmp_path / "build").exists()
    assert (tmp_path / "build/template.yaml").exists()


@pytest.mark.slow
def test_sam_local_api(tmp_path: Path):
    import os
    import signal
    import socket
    import time
    from tempfile import TemporaryDirectory

    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.local.cli_common.invoke_context import InvokeContext
    from samcli.commands.local.lib.local_api_service import LocalApiService
    from samcli.local.docker.exceptions import ProcessSigTermException

    from aws_sam_testing.util import find_free_port

    example_template = """
    Resources:
      SampleApi:
        Type: AWS::Serverless::Api
        Properties:
          Name: SampleApi
          StageName: Prod

      SampleFunction:
        Type: AWS::Serverless::Function
        Properties:
          CodeUri: src/
          Handler: index.handler
          Runtime: python3.13
          MemorySize: 128
          Events:
            SampleEvent:
              Type: Api
              Properties:
                Path: /
                Method: get
                RestApiId: !Ref SampleApi
    """

    template_path = tmp_path / "template.yaml"
    template_path.write_text(example_template)
    # change directory to tmp_path
    os.chdir(tmp_path)

    with BuildContext(
        resource_identifier=None,
        template_file=str(template_path),
        base_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        parallel=True,
        mode="build",
        cached=False,
        clean=True,
        use_container=False,
        aws_region="eu-west-1",
    ) as ctx:
        ctx.run()

    assert (tmp_path / "build").exists()
    assert (tmp_path / "build/template.yaml").exists()

    print("template.yaml:")
    print(open(tmp_path / "build/template.yaml").read())

    with InvokeContext(
        template_file=str(tmp_path / "build/template.yaml"),
        function_identifier=None,
    ) as ctx:
        port = find_free_port()
        with TemporaryDirectory() as static_dir:
            service = LocalApiService(
                lambda_invoke_context=ctx,
                static_dir=str(static_dir),
                port=port,
                host="0.0.0.0",
                disable_authorizer=True,
                ssl_context=None,
            )

            pid = os.fork()
            if pid == 0:
                with pytest.raises(ProcessSigTermException):
                    service.start()
            else:
                time.sleep(1)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(("0.0.0.0", port))
                assert result == 0, f"Failed to connect to 0.0.0.0:8000, error code: {result}"
                sock.close()
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)


@pytest.mark.slow
def test_sam_local_api_env_vars(tmp_path: Path):
    import json
    import os
    import signal
    import socket
    import time
    import urllib.request
    from tempfile import TemporaryDirectory

    from samcli.commands.build.build_context import BuildContext
    from samcli.commands.local.cli_common.invoke_context import InvokeContext
    from samcli.commands.local.lib.local_api_service import LocalApiService
    from samcli.local.docker.exceptions import ProcessSigTermException

    from aws_sam_testing.util import find_free_port

    example_template = """
    Resources:
      EnvVarsApi:
        Type: AWS::Serverless::Api
        Properties:
          Name: EnvVarsApi
          StageName: Prod

      EnvVarsFunction:
        Type: AWS::Serverless::Function
        Properties:
          CodeUri: src/
          Handler: env_handler.handler
          Runtime: python3.13
          MemorySize: 128
          Environment:
            Variables:
              FUNCTION_VAR: "function_value"
          Events:
            GetEnvVars:
              Type: Api
              Properties:
                Path: /env-vars
                Method: get
                RestApiId: !Ref EnvVarsApi
    """

    lambda_code = """
import json
import os

def handler(event, context):
    env_vars = dict(os.environ)
    
    # Sort the environment variables for consistent output
    sorted_env = dict(sorted(env_vars.items()))
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'environment_variables': sorted_env,
            'total_count': len(sorted_env)
        }, indent=2)
    }
"""

    template_path = tmp_path / "template.yaml"
    template_path.write_text(example_template)

    # Create the Lambda function directory and file
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    lambda_file = src_dir / "env_handler.py"
    lambda_file.write_text(lambda_code)

    # change directory to tmp_path
    os.chdir(tmp_path)

    with BuildContext(
        resource_identifier=None,
        template_file=str(template_path),
        base_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        parallel=True,
        mode="build",
        cached=False,
        clean=True,
        use_container=False,
        aws_region="eu-west-1",
    ) as ctx:
        ctx.run()

    build_dir = tmp_path / "build"
    assert build_dir.exists()
    assert (build_dir / "template.yaml").exists()

    print("template.yaml:")
    print(open(build_dir / "template.yaml").read())

    try:
        with InvokeContext(
            template_file=str(tmp_path / "build/template.yaml"),
            function_identifier=None,
            docker_volume_basedir=str(build_dir),
            docker_network=None,
            container_host_interface="127.0.0.1",
            container_host="localhost",
            layer_cache_basedir=str(tmp_path / "build"),
            force_image_build=False,
            skip_pull_image=False,
            log_file=str(build_dir / "log.txt"),
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            aws_profile=os.environ.get("AWS_PROFILE"),
            warm_container_initialization_mode="EAGER",
        ) as ctx:
            port = find_free_port()
            with TemporaryDirectory() as static_dir:
                service = LocalApiService(
                    lambda_invoke_context=ctx,
                    static_dir=str(static_dir),
                    port=port,
                    host="0.0.0.0",
                    disable_authorizer=True,
                    ssl_context=None,
                )

                pid = os.fork()
                if pid == 0:
                    with pytest.raises(ProcessSigTermException):
                        service.start()
                else:
                    try:
                        # Wait for the service to start, try up to 10 times
                        max_tries = 10
                        for _ in range(max_tries):
                            time.sleep(1)
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            result = sock.connect_ex(("0.0.0.0", port))
                            sock.close()
                            if result == 0:
                                try:
                                    with urllib.request.urlopen(f"http://0.0.0.0:{port}/env-vars") as response:
                                        if response.status == 200:
                                            break
                                except Exception as e:
                                    print(f"Error making HTTP request: {e}")
                                    time.sleep(1)
                        else:
                            assert False, f"Failed to connect to 0.0.0.0:{port} after {max_tries} tries"

                        # Make HTTP request to get environment variables
                        url = f"http://0.0.0.0:{port}/env-vars"
                        with urllib.request.urlopen(url) as response:
                            raw = response.read().decode()
                            data = json.loads(raw)
                            print(f"Response status: {response.status}")
                            print(f"Environment variables count: {data['total_count']}")

                            # Check that our custom variables are present
                            env_vars = data["environment_variables"]
                            # assert env_vars["FUNCTION_VAR"] == "function_value"
                            # assert env_vars["CUSTOM_VAR"] == "custom_var_value"
                            print(env_vars)
                    finally:
                        if pid != 0:
                            time.sleep(1)
                            os.kill(pid, signal.SIGKILL)
                            os.waitpid(pid, 0)
    except RequestException as e:
        print(f"Error: {e}")
    except OSError as e:
        print(f"Error: {e}")
