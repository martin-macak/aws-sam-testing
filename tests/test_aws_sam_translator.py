def test_transform():
    import boto3
    from moto import mock_aws
    from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader
    from samtranslator.translator.transform import transform

    template = {
        "Resources": {
            "ExampleFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "Handler": "index.handler",
                    "Runtime": "python3.13",
                    "CodeUri": "s3://test-bucket/test-file.zip",
                },
            },
        },
    }

    with mock_aws():
        session = boto3.Session()
        iam = session.client("iam")

        policy_loader = ManagedPolicyLoader(
            iam_client=iam,
        )

        transformed = transform(
            parameter_values={},
            managed_policy_loader=policy_loader,
            input_fragment=template,
        )

        assert transformed
        example_function_resource = transformed["Resources"]["ExampleFunction"]
        assert example_function_resource["Type"] == "AWS::Lambda::Function"
