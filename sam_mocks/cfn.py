import copy
from typing import Any, Dict, List, Optional, Tuple

import yaml


def get_node_type_name(node: yaml.Node) -> str:
    """Get a human-readable type name for a YAML node."""
    if isinstance(node, yaml.ScalarNode):
        return "scalar"
    elif isinstance(node, yaml.SequenceNode):
        return "sequence"
    elif isinstance(node, yaml.MappingNode):
        return "mapping"
    else:
        return "unknown"


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


class CloudFormationTag:
    """Base class for CloudFormation tags."""

    def __init__(self, value: Any):
        self.value = value

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.value == other.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.value)})"


class RefTag(CloudFormationTag):
    """Represents !Ref tag."""

    pass


class GetAttTag(CloudFormationTag):
    """Represents !GetAtt tag."""

    pass


class SubTag(CloudFormationTag):
    """Represents !Sub tag."""

    pass


class JoinTag(CloudFormationTag):
    """Represents !Join tag."""

    pass


class SplitTag(CloudFormationTag):
    """Represents !Split tag."""

    pass


class SelectTag(CloudFormationTag):
    """Represents !Select tag."""

    pass


class FindInMapTag(CloudFormationTag):
    """Represents !FindInMap tag."""

    pass


class Base64Tag(CloudFormationTag):
    """Represents !Base64 tag."""

    pass


class CidrTag(CloudFormationTag):
    """Represents !Cidr tag."""

    pass


class ImportValueTag(CloudFormationTag):
    """Represents !ImportValue tag."""

    pass


class GetAZsTag(CloudFormationTag):
    """Represents !GetAZs tag."""

    pass


def construct_ref(loader: yaml.Loader, node: yaml.Node) -> RefTag:
    """Construct !Ref tag."""
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a scalar node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    value = loader.construct_scalar(node)
    if value is None or value == "":
        raise yaml.constructor.ConstructorError(None, None, "!Ref tag must not be empty", node.start_mark)
    return RefTag(value)


def construct_get_att(loader: yaml.Loader, node: yaml.Node) -> GetAttTag:
    """Construct !GetAtt tag."""
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a sequence node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    value = loader.construct_sequence(node)
    if len(value) != 2:
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected 2 items in sequence, but found %d" % len(value),
            node.start_mark,
        )
    return GetAttTag(value)


def construct_sub(loader: yaml.Loader, node: yaml.Node) -> SubTag:
    """Construct !Sub tag."""
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
        if value is None or value == "":
            raise yaml.constructor.ConstructorError(None, None, "!Sub tag must not be empty", node.start_mark)
        return SubTag([value])
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
        if len(value) != 2:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "expected 2 items in sequence, but found %d" % len(value),
                node.start_mark,
            )
        return SubTag(value)
    else:
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a scalar or sequence node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )


def construct_join(loader: yaml.Loader, node: yaml.Node) -> JoinTag:
    """Construct !Join tag."""
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a sequence node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    value = loader.construct_sequence(node)
    if len(value) != 2:
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected 2 items in sequence, but found %d" % len(value),
            node.start_mark,
        )
    return JoinTag(value)


def construct_split(loader: yaml.Loader, node: yaml.Node) -> SplitTag:
    """Construct !Split tag."""
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a sequence node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    value = loader.construct_sequence(node)
    if len(value) != 2:
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected 2 items in sequence, but found %d" % len(value),
            node.start_mark,
        )
    return SplitTag(value)


def construct_select(loader: yaml.Loader, node: yaml.Node) -> SelectTag:
    """Construct !Select tag."""
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a sequence node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    value = loader.construct_sequence(node)
    if len(value) != 2:
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected 2 items in sequence, but found %d" % len(value),
            node.start_mark,
        )
    if not isinstance(value[0], int):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected an integer index, but found %s" % type(value[0]).__name__,
            node.start_mark,
        )
    return SelectTag(value)


def construct_find_in_map(loader: yaml.Loader, node: yaml.Node) -> FindInMapTag:
    """Construct !FindInMap tag."""
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a sequence node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    value = loader.construct_sequence(node)
    if len(value) != 3:
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected 3 items in sequence, but found %d" % len(value),
            node.start_mark,
        )
    return FindInMapTag(value)


def construct_base64(loader: yaml.Loader, node: yaml.Node) -> Base64Tag:
    """Construct !Base64 tag."""
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a scalar node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    return Base64Tag(loader.construct_scalar(node))


def construct_cidr(loader: yaml.Loader, node: yaml.Node) -> CidrTag:
    """Construct !Cidr tag."""
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a sequence node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    value = loader.construct_sequence(node)
    if len(value) != 3:
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected 3 items in sequence, but found %d" % len(value),
            node.start_mark,
        )
    return CidrTag(value)


def construct_import_value(loader: yaml.Loader, node: yaml.Node) -> ImportValueTag:
    """Construct !ImportValue tag."""
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a scalar node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    return ImportValueTag(loader.construct_scalar(node))


def construct_get_azs(loader: yaml.Loader, node: yaml.Node) -> GetAZsTag:
    """Construct !GetAZs tag."""
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "expected a scalar node, but found %s" % get_node_type_name(node),
            node.start_mark,
        )
    return GetAZsTag(loader.construct_scalar(node))


class CloudFormationLoader(yaml.SafeLoader):
    """Custom YAML loader that supports CloudFormation tags."""

    pass


# Register CloudFormation tags
CloudFormationLoader.add_constructor("!Ref", construct_ref)
CloudFormationLoader.add_constructor("!GetAtt", construct_get_att)
CloudFormationLoader.add_constructor("!Sub", construct_sub)
CloudFormationLoader.add_constructor("!Join", construct_join)
CloudFormationLoader.add_constructor("!Split", construct_split)
CloudFormationLoader.add_constructor("!Select", construct_select)
CloudFormationLoader.add_constructor("!FindInMap", construct_find_in_map)
CloudFormationLoader.add_constructor("!Base64", construct_base64)
CloudFormationLoader.add_constructor("!Cidr", construct_cidr)
CloudFormationLoader.add_constructor("!ImportValue", construct_import_value)
CloudFormationLoader.add_constructor("!GetAZs", construct_get_azs)


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


class CloudFormationTemplateProcessor:
    """Processor for CloudFormation templates that handles resource manipulation and dependency management."""

    def __init__(self, template: dict[str, Any]):
        """
        Initialize the CloudFormation template processor.

        Args:
            template: The CloudFormation template dictionary to process
        """
        self.template = template
        self.processed_template = copy.deepcopy(template)

    def reset(self):
        self.processed_template = copy.deepcopy(self.template)

    def load_resource_map(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, Any]] = None,
        aws_account_id: Optional[str] = None,
        cross_stack_resources: Optional[Dict[str, Any]] = None,
    ) -> ResourceMap:
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

    def _find_resource_islands(self) -> List[set[str]]:
        """
        Find groups of resources that only reference each other (islands).
        These are resources that form circular references or closed groups.

        Returns:
            List of sets, where each set contains resource names that form an island
        """
        if "Resources" not in self.processed_template:
            return []

        all_resources = set(self.processed_template["Resources"].keys())

        # Build a reference graph
        # references[A] = {B, C} means A references B and C
        # referenced_by[A] = {B, C} means A is referenced by B and C
        references = {}
        referenced_by = {}

        for res_name in all_resources:
            references[res_name] = set()
            referenced_by[res_name] = set()

        # Build the graphs
        for res_name, resource in self.processed_template["Resources"].items():
            for other_res in all_resources:
                if self._find_references_in_value(resource, other_res):
                    references[res_name].add(other_res)
                    referenced_by[other_res].add(res_name)

        # Find resources referenced from outside Resources section
        externally_referenced = set()
        for res_name in all_resources:
            if self._is_resource_referenced_outside_resources(res_name):
                externally_referenced.add(res_name)

        # Find circular reference groups (true islands)
        # These are strongly connected components where no member is referenced from outside
        islands = []

        # Use Tarjan's algorithm to find strongly connected components
        index_counter = [0]
        stack = []
        indices = {}
        lowlinks = {}
        on_stack = {}

        def strongconnect(v):
            indices[v] = index_counter[0]
            lowlinks[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack[v] = True

            # Consider successors of v
            for w in references.get(v, set()):
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif on_stack.get(w, False):
                    lowlinks[v] = min(lowlinks[v], indices[w])

            # If v is a root node, pop the stack and print an SCC
            if lowlinks[v] == indices[v]:
                scc = set()
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.add(w)
                    if w == v:
                        break

                # Check if this SCC is a true island
                is_island = True

                # Single-node SCCs are islands only if they self-reference
                if len(scc) == 1:
                    node = next(iter(scc))
                    # Check if node references itself
                    if node in references.get(node, set()):
                        # It's a self-referencing node
                        if node not in externally_referenced:
                            islands.append(scc)
                elif len(scc) > 1:  # Multi-node SCCs can be circular references
                    # Check if any member is referenced from outside the SCC
                    for node in scc:
                        if node in externally_referenced:
                            is_island = False
                            break

                        # Check references from other resources
                        for ref_by in referenced_by.get(node, set()):
                            if ref_by not in scc:
                                is_island = False
                                break

                        if not is_island:
                            break

                    if is_island:
                        islands.append(scc)

        # Find all SCCs
        for res_name in all_resources:
            if res_name not in indices:
                strongconnect(res_name)

        return islands

    def _is_resource_referenced_outside_resources(self, resource_name: str) -> bool:
        """
        Check if a resource is referenced outside the Resources section.

        Args:
            resource_name: The resource name to check

        Returns:
            True if the resource is referenced in Outputs, Conditions, etc.
        """
        # Check in Outputs section
        if "Outputs" in self.processed_template:
            for output in self.processed_template["Outputs"].values():
                if self._find_references_in_value(output, resource_name):
                    return True

        # Check in Conditions section
        if "Conditions" in self.processed_template:
            for condition in self.processed_template["Conditions"].values():
                if self._find_references_in_value(condition, resource_name):
                    return True

        # Check in Mappings section (unlikely but possible)
        if "Mappings" in self.processed_template:
            for mapping in self.processed_template["Mappings"].values():
                if self._find_references_in_value(mapping, resource_name):
                    return True

        return False

    def remove_resource(
        self,
        resource_name: str,
        auto_remove_dependencies: bool = True,
    ) -> "CloudFormationTemplateProcessor":
        """
        Remove a resource from the template.

        Args:
            resource_name: The name of the resource to remove
            auto_remove_dependencies: If True, automatically remove unreferenced dependencies
                and circular reference islands

        Returns:
            Self for method chaining
        """
        if "Resources" not in self.processed_template or resource_name not in self.processed_template["Resources"]:
            return self

        # If auto_remove_dependencies is True, we need to track what the removed resource depends on
        # before removing it
        dependencies_to_check = set()
        if auto_remove_dependencies:
            # Find all resources that the resource being removed references
            resource = self.processed_template["Resources"][resource_name]
            for other_res in self.processed_template["Resources"]:
                if other_res != resource_name and self._find_references_in_value(resource, other_res):
                    dependencies_to_check.add(other_res)

        # Remove the resource
        self.processed_template["Resources"].pop(resource_name)

        # Now check if any of the dependencies can be removed
        if auto_remove_dependencies and dependencies_to_check:
            # For each dependency, check if it's still needed
            for dep in dependencies_to_check:
                if dep in self.processed_template["Resources"] and not self._is_resource_referenced(dep):
                    # This dependency is no longer referenced, remove it recursively
                    self.remove_resource(dep, auto_remove_dependencies=True)

        # Also check for circular references (islands) that can be removed
        if auto_remove_dependencies:
            self.remove_dependencies(resource_name)

        return self

    def _find_references_in_value(self, value: Any, target_resource: str) -> bool:
        """
        Recursively find if a value contains references to the target resource.

        Args:
            value: The value to check (can be dict, list, scalar, or CloudFormation tag)
            target_resource: The resource name to look for

        Returns:
            True if the value contains a reference to the target resource
        """
        if isinstance(value, RefTag):
            return value.value == target_resource
        elif isinstance(value, GetAttTag):
            return value.value[0] == target_resource
        elif isinstance(value, SubTag):
            # Check if resource is referenced in Sub string
            if len(value.value) == 1:
                # Simple string substitution
                return f"${{{target_resource}}}" in value.value[0] or f"${{!{target_resource}}}" in value.value[0]
            else:
                # String with variable mapping
                if f"${{{target_resource}}}" in value.value[0] or f"${{!{target_resource}}}" in value.value[0]:
                    return True
                # Check variable mapping
                if isinstance(value.value[1], dict):
                    return self._find_references_in_value(value.value[1], target_resource)
        elif isinstance(value, (JoinTag, SplitTag, SelectTag, FindInMapTag, CidrTag)):
            # These tags contain lists/sequences that might contain references
            return self._find_references_in_value(value.value, target_resource)
        elif isinstance(value, (Base64Tag, ImportValueTag, GetAZsTag)):
            # These tags contain single values that might contain references
            return self._find_references_in_value(value.value, target_resource)
        elif isinstance(value, dict):
            # Check Fn:: style functions
            if "Ref" in value and value["Ref"] == target_resource:
                return True
            if "Fn::GetAtt" in value:
                get_att_value = value["Fn::GetAtt"]
                if isinstance(get_att_value, list) and len(get_att_value) > 0 and get_att_value[0] == target_resource:
                    return True
            if "Fn::Sub" in value:
                sub_value = value["Fn::Sub"]
                if isinstance(sub_value, str):
                    return f"${{{target_resource}}}" in sub_value or f"${{!{target_resource}}}" in sub_value
                elif isinstance(sub_value, list) and len(sub_value) > 0:
                    return f"${{{target_resource}}}" in sub_value[0] or f"${{!{target_resource}}}" in sub_value[0]

            # Recursively check all values in the dict
            for v in value.values():
                if self._find_references_in_value(v, target_resource):
                    return True
        elif isinstance(value, list):
            # Recursively check all items in the list
            for item in value:
                if self._find_references_in_value(item, target_resource):
                    return True
        elif isinstance(value, str):
            # Check for string references (unlikely but possible in some contexts)
            return False

        return False

    def _get_resource_dependencies(self, resource_name: str) -> set[str]:
        """
        Get all resources that the given resource depends on.

        Args:
            resource_name: The resource to check dependencies for

        Returns:
            Set of resource names that this resource depends on
        """
        dependencies = set()

        if "Resources" not in self.processed_template:
            return dependencies

        if resource_name not in self.processed_template["Resources"]:
            return dependencies

        resource = self.processed_template["Resources"][resource_name]

        # Check all resources for references
        for res_name in self.processed_template["Resources"]:
            if res_name != resource_name and self._find_references_in_value(resource, res_name):
                dependencies.add(res_name)

        return dependencies

    def _is_resource_referenced(self, resource_name: str) -> bool:
        """
        Check if a resource is referenced anywhere in the template.

        Args:
            resource_name: The resource name to check

        Returns:
            True if the resource is referenced anywhere
        """
        # Check in Resources section
        if "Resources" in self.processed_template:
            for res_name, resource in self.processed_template["Resources"].items():
                if res_name != resource_name and self._find_references_in_value(resource, resource_name):
                    return True

        # Check in Outputs section
        if "Outputs" in self.processed_template:
            for output in self.processed_template["Outputs"].values():
                if self._find_references_in_value(output, resource_name):
                    return True

        # Check in Conditions section
        if "Conditions" in self.processed_template:
            for condition in self.processed_template["Conditions"].values():
                if self._find_references_in_value(condition, resource_name):
                    return True

        # Check in Mappings section (unlikely but possible)
        if "Mappings" in self.processed_template:
            for mapping in self.processed_template["Mappings"].values():
                if self._find_references_in_value(mapping, resource_name):
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

        Args:
            resource_name: Not used - kept for backward compatibility

        Returns:
            Self for method chaining
        """

        islands = self._find_resource_islands()
        for island in islands:
            for resource_name in island:
                if resource_name in self.processed_template["Resources"]:
                    self.processed_template["Resources"].pop(resource_name)

        return self
