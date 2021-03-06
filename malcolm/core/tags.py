import re

from enum import Enum
from annotypes import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Sequence, Union, Tuple, List


def method_return_unpacked():
    """This method has a single element returns, and when called will return
    this single element unpacked rather than in a single element map

    E.g.
       hello.greet("me") -> "Hello me" not {"return": "Hello me"}
    """
    tag = "method:return:unpacked"
    return tag


def group_tag(group_name):
    # type: (str) -> str
    """Marks this field as belonging to a group"""
    tag = "group:%s" % group_name
    return tag


def without_group_tags(tags):
    # type: (Sequence[str]) -> List[str]
    """Return a new list of tags without any group tags"""
    new_tags = [x for x in tags if not x.startswith("group:")]
    return new_tags


def config_tag(iteration=1):
    # type: (int) -> str
    """Marks this field as a value that should be saved and loaded at config

    Args:
        iteration: All iterations are sorted in increasing order and done in
            batches of the same iteration number
    """
    tag = "config:%d" % iteration
    return tag


def get_config_tag(tags):
    # type: (Sequence[str]) -> Union[str, None]
    """Get the config_tag from tags or return None"""
    for tag in tags:
        if tag.startswith("config:"):
            return tag


class Widget(Enum):
    """Enum with all the known widget tags to appear on Attribute Metas"""
    NONE = ""  # Force no widget
    TEXTINPUT = "textinput"  # Editable text input box
    TEXTUPDATE = "textupdate"  # Read only text update
    MULTILINETEXTUPDATE = "multilinetextupdate"  # Multi line text update
    LED = "led"  # On/Off LED indicator
    COMBO = "combo"  # Select from a number of choice values
    ICON = "icon"  # This field gives the URL for an icon for the whole Block
    GROUP = "group"  # Group node in a TreeView that other fields can attach to
    TABLE = "table"  # Table of rows. A list is a single column table
    CHECKBOX = "checkbox"  # A box that can be checked or not
    FLOWGRAPH = "flowgraph"  # Boxes with lines for child block connections
    TREE = "tree"  # A nested tree of object models editor

    def tag(self):
        assert self != Widget.NONE, "Widget.NONE has no widget tag"
        return "widget:%s" % self.value


port_tag_re = re.compile(r"(source|sink)Port:(.*):(.*)")


class Port(Enum):
    """Enum with all the known flowgraph port tags to appear on Attribute
    Metas"""
    BOOL = "bool"  # Boolean
    INT32 = "int32"  # 32-bit signed integer
    NDARRAY = "NDArray"  # areaDetector NDArray port
    MOTOR = "motor"  # motor record connection to CS or controller

    def sink_port_tag(self, disconnected_value):
        """Add a tag indicating this is a Sink Port of the given type

        Args:
            disconnected_value: What value should the Attribute be set to
                when the port is disconnected
        """
        return "sinkPort:%s:%s" % (self.value, disconnected_value)

    def source_port_tag(self, connected_value):
        """Add a tag indicating this is a Source Port of the given type

        Args:
            connected_value: What value should a Sink Port be set to if
                it is connected to this port
        """
        return "sourcePort:%s:%s" % (self.value, connected_value)

    def with_source_port_tag(self, tags, connected_value):
        """Add a Source Port tag to the tags list, removing any other Source
        Ports"""
        new_tags = [t for t in tags if not t.startswith("sourcePort:")]
        new_tags.append(self.source_port_tag(connected_value))
        return new_tags

    @classmethod
    def port_tag_details(cls, tags):
        # type: (Sequence[str]) -> Union[Tuple[bool, Port, str], None]
        """Search tags for port info, returning it

        Args:
            tags: A list of tags to check

        Returns:
            None or (is_source, port, connected_value|disconnected_value)
            where port is one of the Enum entries of Port
        """
        for tag in tags:
            match = port_tag_re.match(tag)
            if match:
                source_sink, port, extra = match.groups()
                return source_sink == "source", cls(port), extra
