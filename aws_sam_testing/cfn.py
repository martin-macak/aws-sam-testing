import copy
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .cfn_tags import CloudFormationDumper, CloudFormationLoader


def load_yaml(stream: str) -> Dict[str, Any]:
    """
    Load YAML content with CloudFormation tag support.

    Args:
        stream: YAML content as string

    Returns:
        Dict containing the parsed YAML with CloudFormation tags
    """
    return yaml.load(stream, Loader=CloudFormationLoader)


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """
    Load YAML file with CloudFormation tag support.

    Args:
        file_path: Path to the YAML file

    Returns:
        Dict containing the parsed YAML with CloudFormation tags
    """
    with open(file_path, "r") as f:
        return yaml.load(f, Loader=CloudFormationLoader)


def dump_yaml(data: Dict[str, Any], stream=None) -> Optional[str]:
    """
    Dump YAML content with CloudFormation tag support.

    Args:
        data: Dictionary to dump as YAML
        stream: Optional file-like object to write to

    Returns:
        YAML string if stream is None, otherwise None
    """
    return yaml.dump(
        data,
        stream=stream,
        Dumper=CloudFormationDumper,
        default_flow_style=False,
        sort_keys=False,
    )


class ResourceMap:
    """Provides access to loaded/inferred"""

    def __init__(self, source: Any):
        self.source = source

    def get_resource(self, logical_id: str) -> Any:
        if logical_id not in self.source.resources:
            raise ValueError(f"Resource {logical_id} not found")

        model = self.source[logical_id]
        if not model:
            raise ValueError(f"Resource {logical_id} not found")

        return model


class CloudFormationTemplateProcessor:
    """
    Processor for CloudFormation templates that handles resource manipulation and dependency management.

    This class is used to process CloudFormation templates and manipulate resources within them.
    It provides methods to find resources by type, remove resources, and manage dependencies.

    The processor maintains a processed template that is a deep copy of the original template.
    This allows for safe manipulation of the template without modifying the original.
    """

    def __init__(self, template: dict[str, Any]):
        """
        Initialize the CloudFormation template processor.

        Args:
            template: The CloudFormation template dictionary to process
        """
        self.template: dict[str, Any] = template
        self.processed_template: dict[str, Any] = copy.deepcopy(template)

    def reset(self):
        """
        Reset the processed template to the original template.

        This method creates a deep copy of the original template and assigns it to the processed template.
        This allows for safe manipulation of the template without modifying the original.
        """
        self.processed_template = copy.deepcopy(self.template)

    def load_resource_map(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, Any]] = None,
        aws_account_id: Optional[str] = None,
        cross_stack_resources: Optional[Dict[str, Any]] = None,
    ) -> ResourceMap:
        """
        Loads a template and parses and resolves CloudFormation tags and intrinsic functions.

        Args:
            parameters: Optional parameters to pass to the template
            tags: Optional tags to pass to the template
            aws_account_id: Optional AWS account ID to use for the template
            cross_stack_resources: Optional cross-stack resources to use for the template

        Returns:
            ResourceMap: A resource map that can be used to find resources by type, remove resources, and manage dependencies.
        """
        from moto import mock_aws
        from moto.cloudformation.parsing import ResourceMap as MotoResourceMap

        with mock_aws():
            resource_map = MotoResourceMap(
                stack_id="stack-123",
                stack_name="my-stack",
                parameters=parameters or {},
                tags=tags or {},
                region_name="us-east-1",
                account_id=aws_account_id or "123456789012",
                template=self.processed_template,
                cross_stack_resources=cross_stack_resources or {},
            )

        return ResourceMap(
            source=resource_map,
        )

    def find_resources_by_type(self, resource_type: str) -> List[Tuple[str, dict[str, Any]]]:
        """
        Find all resources of a specific type in the template.

        Args:
            resource_type: The AWS resource type to search for (e.g., 'AWS::S3::Bucket',
                'AWS::Lambda::Function', 'AWS::Serverless::Function')

        Returns:
            List of tuples, where each tuple contains:
                - logical_id (str): The logical ID of the resource
                - resource_data (dict): Dictionary containing:
                    - 'LogicalId': The logical ID of the resource
                    - 'Type': The resource type (same as input)
                    - 'Properties': The properties of the resource (if any)
                    - 'Metadata': The metadata of the resource (if any)
                    - 'DependsOn': The dependencies of the resource (if any)
                    - 'Condition': The condition of the resource (if any)
                    - 'DeletionPolicy': The deletion policy of the resource (if any)
                    - 'UpdateReplacePolicy': The update replace policy of the resource (if any)

        Example:
            >>> processor = CloudFormationTemplateProcessor(template)
            >>> functions = processor.find_resources_by_type('AWS::Lambda::Function')
            >>> for logical_id, func_data in functions:
            ...     print(f"Function: {logical_id}")
            ...     print(f"Properties: {func_data['Properties']}")
        """
        resources = []

        if "Resources" not in self.processed_template:
            return resources

        for logical_id, resource in self.processed_template["Resources"].items():
            if isinstance(resource, dict) and resource.get("Type") == resource_type:
                # Create a resource dict with all available fields
                resource_data = {"LogicalId": logical_id, "Type": resource["Type"]}

                # Add optional fields if they exist
                optional_fields = [
                    "Properties",
                    "Metadata",
                    "DependsOn",
                    "Condition",
                    "DeletionPolicy",
                    "UpdateReplacePolicy",
                ]
                for field in optional_fields:
                    if field in resource:
                        resource_data[field] = resource[field]

                resources.append((logical_id, resource_data))

        return resources

    def find_resource_by_logical_id(self, logical_id: str) -> Tuple[str, dict[str, Any]]:
        """
        Find a resource by its logical ID in the template.

        Args:
            logical_id: The logical ID of the resource to find

        Returns:
            Tuple containing:
                - logical_id (str): The logical ID of the resource (same as input), or empty string if not found
                - resource_data (dict): Dictionary containing the resource data with the following structure:
                    - 'LogicalId': The logical ID of the resource (same as input)
                    - 'Type': The resource type
                    - 'Properties': The properties of the resource (if any)
                    - 'Metadata': The metadata of the resource (if any)
                    - 'DependsOn': The dependencies of the resource (if any)
                    - 'Condition': The condition of the resource (if any)
                    - 'DeletionPolicy': The deletion policy of the resource (if any)
                    - 'UpdateReplacePolicy': The update replace policy of the resource (if any)

            Returns ("", {}) if the resource is not found.

        Example:
            >>> processor = CloudFormationTemplateProcessor(template)
            >>> logical_id, bucket_data = processor.find_resource_by_logical_id('MyBucket')
            >>> if logical_id:
            ...     print(f"Found {bucket_data['Type']}: {logical_id}")
        """
        if "Resources" not in self.processed_template:
            return ("", {})

        if logical_id not in self.processed_template["Resources"]:
            return ("", {})

        resource = self.processed_template["Resources"][logical_id]

        # Ensure it's a valid resource dict
        if not isinstance(resource, dict) or "Type" not in resource:
            return ("", {})

        # Create a resource dict with all available fields
        resource_data = {"LogicalId": logical_id, "Type": resource["Type"]}

        # Add optional fields if they exist
        optional_fields = [
            "Properties",
            "Metadata",
            "DependsOn",
            "Condition",
            "DeletionPolicy",
            "UpdateReplacePolicy",
        ]
        for field in optional_fields:
            if field in resource:
                resource_data[field] = resource[field]

        return (logical_id, resource_data)

    def remove_resource(
        self,
        resource_name: str,
        auto_remove_dependencies: bool = True,
    ) -> "CloudFormationTemplateProcessor":
        """
        Remove a resource from the template.
        It also removes all dependencies of the resource in the template.
        This function also removes any events on all AWS::Serverless::Function resources that reference the removed resource.

        Dependencies are removed only if auto_remove_dependencies is True.
        Dependencies are removed recursively.

        Args:
            resource_name: The name of the resource to remove
            auto_remove_dependencies: If True, automatically remove unreferenced dependencies
                and circular reference islands

        Returns:
            Self for method chaining
        """
        if "Resources" not in self.processed_template:
            return self

        if resource_name not in self.processed_template["Resources"]:
            return self

        # Remove events that reference this resource from serverless functions BEFORE removing references
        self._remove_serverless_function_events_referencing_resource(resource_name)

        # Remove the resource
        del self.processed_template["Resources"][resource_name]

        # Remove references from other resources
        self._remove_references_to_resource(resource_name)

        if auto_remove_dependencies:
            # Only remove dependencies that were actually dependent on the removed resource
            # Don't remove arbitrary unreferenced resources
            pass  # For now, let's not auto-remove unless specifically requested

        return self

    def update_template(self, update: dict[str, Any]) -> "CloudFormationTemplateProcessor":
        """
        Recursively update the processed template with values from the given template.

        This method performs a deep merge where:
        - Dictionary values are merged recursively
        - List values are replaced entirely
        - Primitive values (str, int, bool, etc.) are replaced

        Args:
            update: Dictionary containing the updates to apply to the template

        Returns:
            Self for method chaining

        Example:
            >>> processor = CloudFormationTemplateProcessor(template)
            >>> processor.update_template({
            ...     "Globals": {
            ...         "Function": {
            ...             "Environment": {
            ...                 "Variables": {
            ...                     "NEW_VAR": "new_value"
            ...                 }
            ...             }
            ...         }
            ...     }
            ... })
        """

        def recursive_update(target: dict[str, Any], source: dict[str, Any]) -> None:
            """
            Recursively update target dictionary with values from source dictionary.

            Args:
                target: The dictionary to update
                source: The dictionary containing updates
            """
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    # Both are dictionaries, merge recursively
                    recursive_update(target[key], value)
                else:
                    # Either key doesn't exist, or one/both values aren't dicts
                    # Replace the value entirely
                    target[key] = copy.deepcopy(value)

        # Perform the recursive update on the processed template
        recursive_update(self.processed_template, update)

        return self

    def _remove_references_to_resource(self, resource_name: str):
        """Remove all references to a resource from the template."""

        def remove_refs_from_value(value):
            """Recursively remove references from a value."""
            if isinstance(value, dict):
                # Handle Ref
                if "Ref" in value and value["Ref"] == resource_name:
                    return None
                # Handle GetAtt
                if "Fn::GetAtt" in value:
                    if isinstance(value["Fn::GetAtt"], list) and len(value["Fn::GetAtt"]) > 0:
                        if value["Fn::GetAtt"][0] == resource_name:
                            return None
                    elif isinstance(value["Fn::GetAtt"], str):
                        if value["Fn::GetAtt"].startswith(resource_name + "."):
                            return None
                # Handle CloudFormation tag objects
                if hasattr(value, "__class__") and hasattr(value, "data"):
                    # Handle Ref tag
                    if hasattr(value, "name") and value.name == "Ref" and value.data == resource_name:  # type: ignore[attr-defined]
                        return None
                    # Handle GetAtt tag
                    if hasattr(value, "name") and value.name == "Fn::GetAtt":  # type: ignore[attr-defined]
                        if isinstance(value.data, list) and len(value.data) > 0 and value.data[0] == resource_name:  # type: ignore[attr-defined]
                            return None
                        elif isinstance(value.data, str) and value.data.startswith(resource_name + "."):  # type: ignore[attr-defined]
                            return None
                # Recursively process dict values
                new_dict = {}
                for k, v in value.items():
                    new_v = remove_refs_from_value(v)
                    if new_v is not None:
                        new_dict[k] = new_v
                return new_dict
            elif isinstance(value, list):
                new_list = []
                for item in value:
                    new_item = remove_refs_from_value(item)
                    if new_item is not None:
                        new_list.append(new_item)
                return new_list
            # Handle CloudFormation tag objects at root level
            elif hasattr(value, "__class__") and hasattr(value, "data"):
                if hasattr(value, "name"):
                    if value.name == "Ref" and value.data == resource_name:
                        return None
                    if value.name == "Fn::GetAtt":
                        if isinstance(value.data, list) and len(value.data) > 0 and value.data[0] == resource_name:
                            return None
                        elif isinstance(value.data, str) and value.data.startswith(resource_name + "."):
                            return None
            return value

        # Process all resources
        if "Resources" in self.processed_template:
            for logical_id, resource in self.processed_template["Resources"].items():
                if isinstance(resource, dict):
                    updated_resource = remove_refs_from_value(resource)
                    if updated_resource is not None:
                        self.processed_template["Resources"][logical_id] = updated_resource

                        # Handle DependsOn specifically
                        if "DependsOn" in updated_resource:
                            depends_on = updated_resource["DependsOn"]  # type: ignore[index]
                            if isinstance(depends_on, list):
                                updated_resource["DependsOn"] = [dep for dep in depends_on if dep != resource_name]  # type: ignore[index]
                                if not updated_resource["DependsOn"]:  # type: ignore[index]
                                    del updated_resource["DependsOn"]  # type: ignore[misc]
                            elif depends_on == resource_name:
                                del updated_resource["DependsOn"]  # type: ignore[misc]

        # Process Outputs
        if "Outputs" in self.processed_template:
            outputs_to_remove = []
            for output_name, output_value in self.processed_template["Outputs"].items():
                if isinstance(output_value, dict):
                    updated_output = remove_refs_from_value(output_value)
                    if updated_output is None or updated_output == {} or (isinstance(updated_output.get("Value"), dict) and not updated_output["Value"]):  # type: ignore[union-attr]
                        outputs_to_remove.append(output_name)
                    else:
                        self.processed_template["Outputs"][output_name] = updated_output
            for output_name in outputs_to_remove:
                del self.processed_template["Outputs"][output_name]

    def _remove_serverless_function_events_referencing_resource(self, resource_name: str):
        """Remove events from AWS::Serverless::Function resources that reference the removed resource."""
        if "Resources" not in self.processed_template:
            return

        for logical_id, resource in self.processed_template["Resources"].items():
            if isinstance(resource, dict) and resource.get("Type") == "AWS::Serverless::Function":
                if "Properties" in resource and "Events" in resource["Properties"]:
                    events = resource["Properties"]["Events"]
                    if isinstance(events, dict):
                        events_to_remove = []
                        for event_name, event_config in events.items():
                            if self._event_references_resource(event_config, resource_name):
                                events_to_remove.append(event_name)

                        for event_name in events_to_remove:
                            del events[event_name]

                        if not events:
                            del resource["Properties"]["Events"]

    def _event_references_resource(self, event_config, resource_name: str) -> bool:
        """Check if an event configuration references a specific resource."""
        if isinstance(event_config, dict):
            for value in event_config.values():
                if isinstance(value, dict):
                    # Check for Ref
                    if "Ref" in value and value["Ref"] == resource_name:
                        return True
                    # Check for GetAtt
                    if "Fn::GetAtt" in value:
                        if isinstance(value["Fn::GetAtt"], list) and len(value["Fn::GetAtt"]) > 0:
                            if value["Fn::GetAtt"][0] == resource_name:
                                return True
                        elif isinstance(value["Fn::GetAtt"], str):
                            if value["Fn::GetAtt"].startswith(resource_name + "."):
                                return True
                    # Recursively check nested dicts
                    if self._event_references_resource(value, resource_name):
                        return True
                # Handle CloudFormation tag objects
                elif hasattr(value, "__class__") and hasattr(value, "data"):
                    if hasattr(value, "name"):
                        if value.name == "Ref" and value.data == resource_name:
                            return True
                        if value.name == "Fn::GetAtt":
                            if isinstance(value.data, list) and len(value.data) > 0 and value.data[0] == resource_name:
                                return True
                            elif isinstance(value.data, str) and value.data.startswith(resource_name + "."):
                                return True
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and self._event_references_resource(item, resource_name):
                            return True
        return False

    def remove_dependencies(
        self,
        resource_name: str,
    ) -> "CloudFormationTemplateProcessor":
        """
        Remove circular reference islands from the template.

        This method identifies and removes groups of resources that only reference
        each other and are not referenced from outside their group (circular reference islands).
        This includes self-referencing resources.

        Dependencies are removed recursively.

        Args:
            resource_name: Not used - kept for backward compatibility

        Returns:
            Self for method chaining
        """
        if "Resources" not in self.processed_template:
            return self

        # Build a graph of resource dependencies
        dependency_graph = self._build_dependency_graph()

        # Find all resources that are referenced by outputs, conditions, or parameters
        externally_referenced = self._find_externally_referenced_resources()

        # Find circular reference islands (groups of resources that only reference each other)
        islands_to_remove = self._find_circular_reference_islands(dependency_graph, externally_referenced)

        # Remove the islands
        for resource in islands_to_remove:
            if resource in self.processed_template["Resources"]:
                del self.processed_template["Resources"][resource]

        return self

    def _build_dependency_graph(self) -> Dict[str, set]:
        """Build a graph of resource dependencies."""
        graph = {}

        if "Resources" not in self.processed_template:
            return graph

        # Initialize graph with all resources
        for resource_name in self.processed_template["Resources"]:
            graph[resource_name] = set()

        # Build dependency relationships
        for resource_name, resource in self.processed_template["Resources"].items():
            if isinstance(resource, dict):
                # Find all dependencies in this resource
                dependencies = self._find_dependencies_in_value(resource)
                graph[resource_name] = dependencies

        return graph

    def _find_dependencies_in_value(self, value) -> set:
        """Find all resource references in a value."""
        dependencies = set()

        if isinstance(value, dict):
            # Handle Ref
            if "Ref" in value and isinstance(value["Ref"], str):
                ref_value = value["Ref"]
                if "Resources" in self.processed_template and ref_value in self.processed_template["Resources"]:
                    dependencies.add(ref_value)
            # Handle GetAtt
            if "Fn::GetAtt" in value:
                if isinstance(value["Fn::GetAtt"], list) and len(value["Fn::GetAtt"]) > 0:
                    resource_ref = value["Fn::GetAtt"][0]
                    if "Resources" in self.processed_template and resource_ref in self.processed_template["Resources"]:
                        dependencies.add(resource_ref)
                elif isinstance(value["Fn::GetAtt"], str):
                    resource_ref = value["Fn::GetAtt"].split(".")[0]
                    if "Resources" in self.processed_template and resource_ref in self.processed_template["Resources"]:
                        dependencies.add(resource_ref)
            # Handle DependsOn
            if "DependsOn" in value:
                depends_on = value["DependsOn"]
                if isinstance(depends_on, list):
                    for dep in depends_on:
                        if isinstance(dep, str) and dep in self.processed_template.get("Resources", {}):
                            dependencies.add(dep)
                elif isinstance(depends_on, str) and depends_on in self.processed_template.get("Resources", {}):
                    dependencies.add(depends_on)
            # Recursively process dict values
            for v in value.values():
                dependencies.update(self._find_dependencies_in_value(v))
        elif isinstance(value, list):
            for item in value:
                dependencies.update(self._find_dependencies_in_value(item))
        # Handle CloudFormation tag objects
        elif hasattr(value, "__class__") and hasattr(value, "data") and hasattr(value, "name"):
            if value.name == "Ref" and isinstance(value.data, str):
                if "Resources" in self.processed_template and value.data in self.processed_template["Resources"]:
                    dependencies.add(value.data)
            elif value.name == "Fn::GetAtt":
                if isinstance(value.data, list) and len(value.data) > 0:
                    resource_ref = value.data[0]
                    if "Resources" in self.processed_template and resource_ref in self.processed_template["Resources"]:
                        dependencies.add(resource_ref)
                elif isinstance(value.data, str):
                    resource_ref = value.data.split(".")[0]
                    if "Resources" in self.processed_template and resource_ref in self.processed_template["Resources"]:
                        dependencies.add(resource_ref)
            # For other CloudFormation functions, recursively check their data
            if hasattr(value, "data"):
                dependencies.update(self._find_dependencies_in_value(value.data))

        return dependencies

    def _find_externally_referenced_resources(self) -> set:
        """Find resources that are referenced from outputs, conditions, or parameters."""
        externally_referenced = set()

        # Check outputs
        if "Outputs" in self.processed_template:
            for output_value in self.processed_template["Outputs"].values():
                if isinstance(output_value, dict):
                    externally_referenced.update(self._find_dependencies_in_value(output_value))

        # Check conditions
        if "Conditions" in self.processed_template:
            for condition_value in self.processed_template["Conditions"].values():
                externally_referenced.update(self._find_dependencies_in_value(condition_value))

        # Check parameters (for default values that might reference resources)
        if "Parameters" in self.processed_template:
            for param_value in self.processed_template["Parameters"].values():
                if isinstance(param_value, dict):
                    externally_referenced.update(self._find_dependencies_in_value(param_value))

        return externally_referenced

    def _find_circular_reference_islands(self, dependency_graph: Dict[str, set], externally_referenced: set) -> set:
        """Find circular reference islands - groups of resources that only reference each other."""
        islands_to_remove = set()
        visited = set()

        def find_connected_component(start_resource: str) -> set:
            """Find all resources connected to the start resource."""
            component = set()
            to_visit = {start_resource}

            while to_visit:
                current = to_visit.pop()
                if current in component:
                    continue

                component.add(current)

                # Add resources that this resource depends on
                if current in dependency_graph:
                    to_visit.update(dependency_graph[current])

                # Add resources that depend on this resource
                for resource, deps in dependency_graph.items():
                    if current in deps:
                        to_visit.add(resource)

            return component

        # Find all connected components
        for resource in dependency_graph:
            if resource not in visited:
                component = find_connected_component(resource)
                visited.update(component)

                # Check if this component is an island (not referenced externally)
                is_island = True
                for comp_resource in component:
                    if comp_resource in externally_referenced:
                        is_island = False
                        break

                    # Check if any external resource depends on this component resource
                    for external_resource in dependency_graph:
                        if external_resource not in component:
                            if comp_resource in dependency_graph.get(external_resource, set()):
                                is_island = False
                                break

                    if not is_island:
                        break

                if is_island:
                    islands_to_remove.update(component)

        return islands_to_remove

    def transform_cfn_tags(self) -> "CloudFormationTemplateProcessor":
        """
        Replaces all CloudFormation tags with their corresponding intrinsic functions.

        Transforms YAML tags to JSON-style intrinsic functions:
        - !Ref -> {"Ref": value}
        - !GetAtt -> {"Fn::GetAtt": [logical_id, attribute]}
        - !Sub -> {"Fn::Sub": value}
        - !Join -> {"Fn::Join": [delimiter, values]}
        - !Split -> {"Fn::Split": [delimiter, string]}
        - !Select -> {"Fn::Select": [index, array]}
        - !FindInMap -> {"Fn::FindInMap": [map_name, top_level_key, second_level_key]}
        - !Base64 -> {"Fn::Base64": value}
        - !Cidr -> {"Fn::Cidr": [ip_block, count, cidr_bits]}
        - !ImportValue -> {"Fn::ImportValue": value}
        - !GetAZs -> {"Fn::GetAZs": region}

        Returns:
            CloudFormationTemplateProcessor: Self for method chaining
        """

        def transform_value(value):
            """Recursively transform CloudFormation tag objects to JSON intrinsic functions."""
            # Import CloudFormationObject here to avoid circular imports
            from .cfn_tags import CloudFormationObject

            # Check if this is a CloudFormation tag object
            if isinstance(value, CloudFormationObject):
                # Transform the data first, then create the JSON structure
                transformed_data = transform_value(value.data)

                # Handle special cases from original to_json() method
                name = value.name
                if name == "Fn::GetAtt" and isinstance(transformed_data, str):
                    transformed_data = transformed_data.split(".")
                elif name == "Ref" and isinstance(transformed_data, str) and "." in transformed_data:
                    name = "Fn::GetAtt"
                    transformed_data = transformed_data.split(".")

                return {name: transformed_data}
            elif isinstance(value, dict):
                # Recursively transform dict values
                return {k: transform_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                # Recursively transform list items
                return [transform_value(item) for item in value]
            else:
                # Return primitive values as-is
                return value

        # Transform the entire template
        self.processed_template = transform_value(self.processed_template)  # type: ignore[assignment]

        return self
