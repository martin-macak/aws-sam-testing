# Isolated tests

These tests are run in docker so we can test that the code and test works without any AWS_PROFILE or AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY
or anything that can leak or interfere with the real AWS account or localstack.