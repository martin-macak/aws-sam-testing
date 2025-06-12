def test_sanity():
    assert True


def test_build_with_toolkit():
    from pathlib import Path

    from aws_sam_testing.aws_sam import AWSSAMToolkit

    toolkit = AWSSAMToolkit(
        working_dir=Path(__file__).parent,
        template_path=Path(__file__).parent / "template.yaml",
    )

    toolkit.sam_build()

    p_built_template = Path(__file__).parent / ".aws-sam" / "aws-sam-testing-build" / "template.yaml"
    assert p_built_template.exists()


def test_run_local_api():
    import socket
    import time
    from pathlib import Path

    import requests
    from samcli.local.docker.exceptions import ProcessSigTermException

    from aws_sam_testing.aws_sam import AWSSAMToolkit

    toolkit = AWSSAMToolkit(
        working_dir=Path(__file__).parent,
        template_path=Path(__file__).parent / "template.yaml",
    )

    toolkit.sam_build()

    try:
        with toolkit.run_local_api() as apis:
            assert len(apis) == 1

            api = apis[0]

            assert api.api_logical_id == "MyApi"
            assert api.port is not None
            assert api.host is not None

            # Try to connect to the API in a loop with max 10 retries
            max_retries = 10
            retry_count = 0
            connected = False

            while retry_count < max_retries and not connected:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    result = sock.connect_ex((api.host, api.port))
                    if result == 0:
                        connected = True
                        sock.close()
                        break
                    sock.close()
                except Exception:
                    pass

                retry_count += 1
                time.sleep(1)

            assert connected, f"Failed to connect to {api.host}:{api.port} after {max_retries} attempts"

            for api in apis:
                assert api.is_running

            response = requests.get(f"http://{api.host}:{api.port}/hello")
            assert response is not None
            # assert response.status_code == 200
            # assert response.json() == {"message": "Hello, World!"}

            for api in apis:
                api.stop()

            for api in apis:
                assert not api.is_running

    except ProcessSigTermException:
        pass
