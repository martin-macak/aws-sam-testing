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

            api.wait_for_api_to_be_ready()

            for api in apis:
                assert api.is_running

            response = requests.get(f"http://{api.host}:{api.port}/hello")
            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"message": "Hello World!"}

            for api in apis:
                api.stop()

            for api in apis:
                assert not api.is_running

    except ProcessSigTermException:
        pass
