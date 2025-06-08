from pathlib import Path

import pytest


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
                os.kill(pid, signal.SIGTERM)
