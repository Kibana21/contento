"""A strict recogniser for authored markup — not a forgiving sanitiser.

The free-form engine lets a model author structure, never content (plan §1). This parser is
the first line enforcing that: it accepts a closed subset of HTML and *rejects* anything else
rather than repairing it. Rejection is the right behaviour — the model gets the parse error
back as a repair finding, and there is no silent-fixup path for a compliance reviewer to
distrust.

The guarantee itself is the render-time audit in `renderer.py`, which inspects pseudo-element
content and probes for occlusion. This layer is defence in depth: it catches the obvious
vectors cheaply and offline, with no browser launch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

#: Elements the author may use. Deliberately small.
#:   * `hr` stays: it is the hairline divider in the reference brochures and renders no text.
#:   * `ul`/`ol`/`li` are absent, which removes the whole list-marker text vector; a list here
#:     is a div of divs.
#:   * `svg` is absent, so a model can never draw paths or emit `<text>`/`<tspan>`.
#:   * Form and embedding elements are absent: several render browser-supplied default labels.
ALLOWED_TAGS = frozenset({
    "div", "section", "header", "footer", "article", "span", "p",
    "h1", "h2", "h3", "figure", "figcaption", "img", "hr", "br",
})

#: Elements with no closing tag.
VOID_TAGS = frozenset({"img", "hr", "br"})

#: Attributes the author may set. `id` is absent on purpose — the binder assigns ids, and only
#: to bound leaves, so the measured element set contains no ancestor/descendant pairs (plan §3.4).
#: `style` is absent so the repair layer owns it exclusively. `alt`/`title` are absent because
#: they render as visible text when an image fails to load.
ALLOWED_ATTRS = frozenset({"class", "data-ref", "data-asset", "data-group", "data-tint"})

#: Whitespace, spelled out. NOT `str.isspace()`: that returns True for U+00A0 (`&nbsp;`), which
#: would let an unlimited flood of non-breaking spaces through as layout manipulation.
WHITESPACE = frozenset(" \t\n\r")

#: Class names are restricted so that a class can never break out of a CSS selector when the
#: stylesheet is serialised.
_CLASS_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789- ")


class AuthoredHtmlError(ValueError):
    """The authored markup left the accepted subset. Reported to the model as a finding."""

    def __init__(self, rule_id: str, message: str, *, line: int = 0) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message
        self.line = line


@dataclass
class Node:
    """One accepted element. The binder walks this tree; the raw string is never re-parsed."""

    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)

    @property
    def ref(self) -> str | None:
        return self.attrs.get("data-ref")

    @property
    def asset(self) -> str | None:
        return self.attrs.get("data-asset")

    @property
    def is_bound(self) -> bool:
        """Bound leaves are the nodes the binder fills and the validators measure."""
        return bool(self.ref or self.asset)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


class _Recogniser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)  # we must see charrefs to reject them
        self.root = Node("root")
        self._stack: list[Node] = [self.root]

    # ---- the core rule: the author may not write text ---------------------
    def handle_data(self, data: str) -> None:
        if set(data) - WHITESPACE:
            raise AuthoredHtmlError(
                "authored.text",
                f"authored markup may not contain text: {data.strip()[:60]!r}",
                line=self.getpos()[0],
            )

    def handle_entityref(self, name: str) -> None:
        # `&nbsp;` / `&amp;` never reach handle_data, so they need their own guard.
        raise AuthoredHtmlError("authored.text",
                                f"entity reference &{name}; is text", line=self.getpos()[0])

    def handle_charref(self, name: str) -> None:
        # `&#48;&#46;&#51;&#53;&#37;` renders as "0.35%" but is not a text node.
        raise AuthoredHtmlError("authored.text",
                                f"character reference &#{name}; is text", line=self.getpos()[0])

    def handle_comment(self, data: str) -> None:
        raise AuthoredHtmlError("authored.comment", "comments are not allowed",
                                line=self.getpos()[0])

    def handle_decl(self, decl: str) -> None:
        raise AuthoredHtmlError("authored.decl", f"declaration <!{decl[:40]}> is not allowed",
                                line=self.getpos()[0])

    def handle_pi(self, data: str) -> None:
        raise AuthoredHtmlError("authored.decl", "processing instructions are not allowed",
                                line=self.getpos()[0])

    # ---- structure --------------------------------------------------------
    def handle_starttag(self, tag: str, attrs) -> None:
        node = Node(tag=tag, attrs=self._check(tag, attrs))
        self._stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self._stack[-1].children.append(Node(tag=tag, attrs=self._check(tag, attrs)))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if len(self._stack) < 2 or self._stack[-1].tag != tag:
            open_tag = self._stack[-1].tag if len(self._stack) > 1 else "nothing"
            raise AuthoredHtmlError(
                "authored.unbalanced",
                f"</{tag}> closes {open_tag}; tags must nest properly",
                line=self.getpos()[0],
            )
        self._stack.pop()

    def _check(self, tag: str, attrs) -> dict[str, str]:
        line = self.getpos()[0]
        if tag not in ALLOWED_TAGS:
            raise AuthoredHtmlError("authored.tag",
                                    f"<{tag}> is not an allowed element", line=line)
        out: dict[str, str] = {}
        for name, value in attrs:
            if name not in ALLOWED_ATTRS:
                raise AuthoredHtmlError(
                    "authored.attribute",
                    f"<{tag} {name}=...> is not allowed; "
                    f"assets come from data-asset and ids are assigned by the binder",
                    line=line,
                )
            value = value or ""
            if name == "class" and set(value.lower()) - _CLASS_CHARS:
                raise AuthoredHtmlError("authored.attribute",
                                        f"class {value!r} may use only a-z, 0-9 and '-'", line=line)
            if name in out:
                raise AuthoredHtmlError("authored.attribute",
                                        f"duplicate attribute {name!r}", line=line)
            out[name] = value
        return out


def parse_authored(html: str) -> Node:
    """Parse authored markup into a node tree, or raise `AuthoredHtmlError`.

    A parser differential between `html.parser` here and Chromium later can only produce a
    false *rejection*, never a false acceptance, because the render-time audit runs on the
    document Chromium actually built. For a governed system that is the safe direction.
    """
    parser = _Recogniser()
    parser.feed(html)
    parser.close()
    if len(parser._stack) != 1:
        unclosed = ", ".join(f"<{n.tag}>" for n in parser._stack[1:])
        raise AuthoredHtmlError("authored.unbalanced", f"unclosed element(s): {unclosed}")
    return parser.root


def serialise(node: Node) -> str:
    """Re-emit the accepted tree. Output comes from the parsed nodes, never the input string."""
    if node.tag == "root":
        return "".join(serialise(c) for c in node.children)
    attrs = "".join(f' {k}="{_escape(v)}"' for k, v in sorted(node.attrs.items()) if v != "")
    if node.tag in VOID_TAGS:
        return f"<{node.tag}{attrs}>"
    inner = "".join(serialise(c) for c in node.children)
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
