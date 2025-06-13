def test_mock_aws_resources(
    mock_aws_session,
    mock_aws_resources,
    aws_region,
):
    assert mock_aws_resources is not None

    sqs = mock_aws_session.client("sqs")
    queues = sqs.list_queues()
    assert len(queues["QueueUrls"]) == 1
    queue_url = queues["QueueUrls"][0]
    assert queue_url == f"https://sqs.{aws_region}.amazonaws.com/123456789012/my-queue"
