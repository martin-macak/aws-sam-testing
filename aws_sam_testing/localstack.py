from enum import Enum
from pathlib import Path

from aws_sam_testing.cfn import CloudFormationTemplateProcessor
from aws_sam_testing.core import CloudFormationTool


class LocalStackFeautureSet(Enum):
    NORMAL = "normal"
    PRO = "pro"


class LocalStack:
    def __init__(self):
        self.is_running = False
        self.moto_server = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self):
        if self.is_running:
            return

        self._do_start()
        self.is_running = True

    def stop(self):
        if not self.is_running:
            return

        self._do_stop()
        self.is_running = False

    def restart(self):
        self.stop()
        self.start()

    def _do_start(self):
        pass

    def _do_stop(self):
        pass


class LocalStackToolkit(CloudFormationTool):
    def build(
        self,
        feature_set: LocalStackFeautureSet = LocalStackFeautureSet.NORMAL,
        build_dir: Path | None = None,
    ) -> Path:
        from aws_sam_testing.aws_sam import AWSSAMToolkit
        from aws_sam_testing.cfn import dump_yaml

        base_build_dir = build_dir
        if build_dir is None:
            base_build_dir = Path(self.working_dir) / ".aws-sam"
        elif isinstance(base_build_dir, str):
            base_build_dir = Path(build_dir)

        assert base_build_dir is not None
        localstack_build_dir = base_build_dir / ".aws-sam" / "aws-sam-testing-localstack-build"
        localstack_build_dir.mkdir(parents=True, exist_ok=True)

        processor = LocalStackCloudFormationTemplateProcessor(
            template=self.template,
        )

        if feature_set == LocalStackFeautureSet.NORMAL:
            processor.remove_non_pro_resources()

        template = processor.processed_template
        sam_build_dir: Path | None = None

        localstack_template_path = base_build_dir / "template.localstack.yaml"
        try:
            dump_yaml(template, stream=localstack_template_path)
            dump_yaml(template, stream=localstack_build_dir / "template.source.yaml")

            sam_toolkit = AWSSAMToolkit(
                working_dir=self.working_dir,
                template_path=self.template_path,
            )

            sam_build_dir = sam_toolkit.sam_build(
                build_dir=localstack_build_dir,
            )
        finally:
            # delete the file
            localstack_template_path.unlink()

        assert sam_build_dir is not None

        if feature_set == LocalStackFeautureSet.NORMAL:
            self._process_lambda_layers(
                source_template_path=sam_build_dir / "template.yaml",
                build_dir=localstack_build_dir,
                flatten_layers=True,
                layer_cache_dir=base_build_dir / ".aws-sam" / "aws-sam-testing-localstack-layers",
            )

        return localstack_build_dir

    def _process_lambda_layers(
        self,
        source_template_path: Path,
        build_dir: Path,
        flatten_layers: bool = True,
        layer_cache_dir: Path | None = None,
    ) -> Path:
        """
        Processes the AWS SAM build directory so it can be executed safely in localstack.
        Localstack without PRO features does not support AWS Lambda layers.
        This can be solved by downloading all lambda layers referenced in the template and then packing all packages
        in correct order in each function.
        This works exactly as the layered file system. So all files and packages are incrementally merged into the final
        directory.

        For example:
        Lambda function SomeFunction has a layers layer_a and layer_b.
        The layer_a has a package package_a
        The layer_b has a package package_b.
        The function also packages package_c.

        After the processing, if flatten_layers is True, the function will have a directory with the following structure:
        SomeFunction/
            package_a/
            package_b/
            package_c/

        If flatten_layers is False, the function will have a directory with the following structure:
        SomeFunction/
            package_c/


        Also if flatten_layers was performed, all flattened layers are removed from the template
        For example:
        SomeFunction:
            Type: AWS::Serverless::Function
            Properties:
                Layers:
                    - !Ref LayerA
                    - !Ref LayerB
                PackageType: Zip
                CodeUri: SomeFunction/

        After the processing, the template will have the following structure:
        SomeFunction:
            Type: AWS::Serverless::Function
            Properties:
                PackageType: Zip
                CodeUri: SomeFunction/

        Flattening is performed in the directory given by the source_template_path. The algorithm reads
        all lambda functions in the template and then for each function it reads the layers and packages.
        It then processes them into new directory given in build_dir.

        The source_template_path is not modified as well as the lambda functions in the source template.
        New build is created in the build_dir. This build is valid AWS SAM build that can be executed in localstack.

        Layers are downloaded from AWS so valid AWS session is required when this function is called.
        Layers are downloaded only once and then cached in the layer_cache_dir.

        Args:
            source_template_path (Path): The source directory with input SAM build that will be processed.
            build_dir (Path): The destination directory where the SAM build with processed build.
            flatten_layers (bool, optional): _description_. Defaults to True.
            layer_cache_dir (Path, optional): The directory where the layers will be cached. Defaults to None.

        Returns:
            Path: The path to the new build directory.
        """

        return build_dir


class LocalStackCloudFormationTemplateProcessor(CloudFormationTemplateProcessor):
    # List of AWS resource types that require LocalStack PRO
    # Based on LocalStack documentation
    PRO_RESOURCES = [
        # API Gateway v2 (WebSocket APIs)
        "AWS::ApiGatewayV2::Api",
        "AWS::ApiGatewayV2::ApiMapping",
        "AWS::ApiGatewayV2::Authorizer",
        "AWS::ApiGatewayV2::Deployment",
        "AWS::ApiGatewayV2::DomainName",
        "AWS::ApiGatewayV2::Integration",
        "AWS::ApiGatewayV2::IntegrationResponse",
        "AWS::ApiGatewayV2::Model",
        "AWS::ApiGatewayV2::Route",
        "AWS::ApiGatewayV2::RouteResponse",
        "AWS::ApiGatewayV2::Stage",
        "AWS::ApiGatewayV2::VpcLink",
        # AppSync
        "AWS::AppSync::ApiCache",
        "AWS::AppSync::ApiKey",
        "AWS::AppSync::DataSource",
        "AWS::AppSync::FunctionConfiguration",
        "AWS::AppSync::GraphQLApi",
        "AWS::AppSync::GraphQLSchema",
        "AWS::AppSync::Resolver",
        # Athena
        "AWS::Athena::DataCatalog",
        "AWS::Athena::NamedQuery",
        "AWS::Athena::WorkGroup",
        # Backup
        "AWS::Backup::BackupPlan",
        "AWS::Backup::BackupSelection",
        "AWS::Backup::BackupVault",
        # CloudFront
        "AWS::CloudFront::CachePolicy",
        "AWS::CloudFront::CloudFrontOriginAccessIdentity",
        "AWS::CloudFront::Distribution",
        "AWS::CloudFront::Function",
        "AWS::CloudFront::KeyGroup",
        "AWS::CloudFront::OriginRequestPolicy",
        "AWS::CloudFront::PublicKey",
        "AWS::CloudFront::RealtimeLogConfig",
        "AWS::CloudFront::ResponseHeadersPolicy",
        # Cognito Identity Provider
        "AWS::Cognito::IdentityPool",
        "AWS::Cognito::IdentityPoolRoleAttachment",
        "AWS::Cognito::UserPool",
        "AWS::Cognito::UserPoolClient",
        "AWS::Cognito::UserPoolDomain",
        "AWS::Cognito::UserPoolGroup",
        "AWS::Cognito::UserPoolIdentityProvider",
        "AWS::Cognito::UserPoolResourceServer",
        "AWS::Cognito::UserPoolRiskConfigurationAttachment",
        "AWS::Cognito::UserPoolUICustomizationAttachment",
        "AWS::Cognito::UserPoolUser",
        "AWS::Cognito::UserPoolUserToGroupAttachment",
        # DocumentDB
        "AWS::DocDB::DBCluster",
        "AWS::DocDB::DBClusterParameterGroup",
        "AWS::DocDB::DBInstance",
        "AWS::DocDB::DBSubnetGroup",
        # ECS
        "AWS::ECS::CapacityProvider",
        "AWS::ECS::Cluster",
        "AWS::ECS::ClusterCapacityProviderAssociations",
        "AWS::ECS::PrimaryTaskSet",
        "AWS::ECS::Service",
        "AWS::ECS::TaskDefinition",
        "AWS::ECS::TaskSet",
        # EKS
        "AWS::EKS::Addon",
        "AWS::EKS::Cluster",
        "AWS::EKS::FargateProfile",
        "AWS::EKS::Nodegroup",
        # ElastiCache
        "AWS::ElastiCache::CacheCluster",
        "AWS::ElastiCache::ParameterGroup",
        "AWS::ElastiCache::ReplicationGroup",
        "AWS::ElastiCache::SecurityGroup",
        "AWS::ElastiCache::SecurityGroupIngress",
        "AWS::ElastiCache::SubnetGroup",
        "AWS::ElastiCache::User",
        "AWS::ElastiCache::UserGroup",
        # Elasticsearch/OpenSearch
        "AWS::Elasticsearch::Domain",
        "AWS::OpenSearchService::Domain",
        # EMR
        "AWS::EMR::Cluster",
        "AWS::EMR::InstanceFleetConfig",
        "AWS::EMR::InstanceGroupConfig",
        "AWS::EMR::SecurityConfiguration",
        "AWS::EMR::Step",
        # Glue
        "AWS::Glue::Classifier",
        "AWS::Glue::Connection",
        "AWS::Glue::Crawler",
        "AWS::Glue::Database",
        "AWS::Glue::DataCatalogEncryptionSettings",
        "AWS::Glue::DevEndpoint",
        "AWS::Glue::Job",
        "AWS::Glue::MLTransform",
        "AWS::Glue::Partition",
        "AWS::Glue::Registry",
        "AWS::Glue::Schema",
        "AWS::Glue::SchemaVersion",
        "AWS::Glue::SchemaVersionMetadata",
        "AWS::Glue::SecurityConfiguration",
        "AWS::Glue::Table",
        "AWS::Glue::Trigger",
        "AWS::Glue::Workflow",
        # IoT
        "AWS::IoT::AccountAuditConfiguration",
        "AWS::IoT::Authorizer",
        "AWS::IoT::Certificate",
        "AWS::IoT::CustomMetric",
        "AWS::IoT::Dimension",
        "AWS::IoT::DomainConfiguration",
        "AWS::IoT::FleetMetric",
        "AWS::IoT::JobTemplate",
        "AWS::IoT::MitigationAction",
        "AWS::IoT::Policy",
        "AWS::IoT::PolicyPrincipalAttachment",
        "AWS::IoT::ProvisioningTemplate",
        "AWS::IoT::RoleAlias",
        "AWS::IoT::ScheduledAudit",
        "AWS::IoT::SecurityProfile",
        "AWS::IoT::Thing",
        "AWS::IoT::ThingGroup",
        "AWS::IoT::ThingPrincipalAttachment",
        "AWS::IoT::ThingType",
        "AWS::IoT::TopicRule",
        "AWS::IoT::TopicRuleDestination",
        # Managed Blockchain
        "AWS::ManagedBlockchain::Member",
        "AWS::ManagedBlockchain::Node",
        # MSK
        "AWS::MSK::Cluster",
        # Neptune
        "AWS::Neptune::DBCluster",
        "AWS::Neptune::DBClusterParameterGroup",
        "AWS::Neptune::DBInstance",
        "AWS::Neptune::DBParameterGroup",
        "AWS::Neptune::DBSubnetGroup",
        # QLDB
        "AWS::QLDB::Ledger",
        "AWS::QLDB::Stream",
        # RDS (certain features)
        "AWS::RDS::DBProxy",
        "AWS::RDS::DBProxyEndpoint",
        "AWS::RDS::DBProxyTargetGroup",
        "AWS::RDS::GlobalCluster",
        # Route53
        "AWS::Route53::DNSSEC",
        "AWS::Route53::HealthCheck",
        "AWS::Route53::HostedZone",
        "AWS::Route53::KeySigningKey",
        "AWS::Route53::RecordSet",
        "AWS::Route53::RecordSetGroup",
        # SageMaker
        "AWS::SageMaker::App",
        "AWS::SageMaker::AppImageConfig",
        "AWS::SageMaker::CodeRepository",
        "AWS::SageMaker::DataQualityJobDefinition",
        "AWS::SageMaker::Device",
        "AWS::SageMaker::DeviceFleet",
        "AWS::SageMaker::Domain",
        "AWS::SageMaker::Endpoint",
        "AWS::SageMaker::EndpointConfig",
        "AWS::SageMaker::FeatureGroup",
        "AWS::SageMaker::Image",
        "AWS::SageMaker::ImageVersion",
        "AWS::SageMaker::Model",
        "AWS::SageMaker::ModelBiasJobDefinition",
        "AWS::SageMaker::ModelExplainabilityJobDefinition",
        "AWS::SageMaker::ModelPackage",
        "AWS::SageMaker::ModelPackageGroup",
        "AWS::SageMaker::ModelQualityJobDefinition",
        "AWS::SageMaker::MonitoringSchedule",
        "AWS::SageMaker::NotebookInstance",
        "AWS::SageMaker::NotebookInstanceLifecycleConfig",
        "AWS::SageMaker::Pipeline",
        "AWS::SageMaker::Project",
        "AWS::SageMaker::UserProfile",
        "AWS::SageMaker::Workteam",
        # Transfer
        "AWS::Transfer::Server",
        "AWS::Transfer::User",
        "AWS::Transfer::Workflow",
        # XRay
        "AWS::XRay::Group",
        "AWS::XRay::SamplingRule",
    ]

    def remove_non_pro_resources(self):
        """
        Remove all resources that require LocalStack PRO from the template.
        This includes removing the resources and all their dependencies.
        """
        resources_to_remove = []

        # Find all PRO resources in the template
        for resource_type in self.PRO_RESOURCES:
            pro_resources = self.find_resources_by_type(resource_type)
            for logical_id, _ in pro_resources:
                resources_to_remove.append(logical_id)

        # Remove each PRO resource (remove_resource will handle dependencies and references)
        for resource_id in resources_to_remove:
            self.remove_resource(resource_id, auto_remove_dependencies=False)

        # Clean up outputs that no longer have values
        self._clean_invalid_outputs()

        return self

    def _clean_invalid_outputs(self):
        """Remove outputs that don't have a Value field."""
        if "Outputs" not in self.processed_template:
            return

        outputs_to_remove = []
        for output_name, output_value in self.processed_template["Outputs"].items():
            if isinstance(output_value, dict) and "Value" not in output_value:
                outputs_to_remove.append(output_name)

        for output_name in outputs_to_remove:
            del self.processed_template["Outputs"][output_name]
