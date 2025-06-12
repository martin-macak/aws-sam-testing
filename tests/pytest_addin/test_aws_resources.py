def test_mock_aws_resources(
    mock_aws_session,
    mock_aws_resources,
):
    assert mock_aws_resources is not None

    sqs = mock_aws_session.client("sqs")
    queues = sqs.list_queues()
    assert len(queues["QueueUrls"]) == 1
    queue_url = queues["QueueUrls"][0]
    assert queue_url == "https://sqs.eu-west-1.amazonaws.com/123456789012/my-queue"
