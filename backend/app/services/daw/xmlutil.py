"""XML helpers shared by the namespace-agnostic DAW parsers."""
import xml.etree.ElementTree as ET


def local_name(tag: str) -> str:
    """Tag name without its `{namespace}` prefix."""
    return tag.rsplit("}", 1)[-1]


def first_descendant(el: ET.Element, local_tag: str) -> ET.Element | None:
    """First element at or below `el` whose local tag name matches."""
    for child in el.iter():
        if local_name(child.tag) == local_tag:
            return child
    return None
