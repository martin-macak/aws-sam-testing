from pathlib import Path


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
