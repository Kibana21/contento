"""The shared class vocabulary and reference typing.

Two independent model calls author the stylesheet and the markup. These tests cover the
machinery that makes them agree, and the derivation that stops a model relabelling a
disclaimer as decoration.
"""

from __future__ import annotations

import pytest

from src.contracts.design import ElementType
from src.freeform.html_parse import parse_authored
from src.freeform.vocabulary import (CORE_CLASSES, MAX_CUSTOM_CLASSES, VocabularyError,
                                     classes_targeted, classes_used, element_type_for,
                                     vocabulary_for)


class TestVocabulary:
    def test_core_classes_are_available_without_extensions(self):
        assert vocabulary_for() == CORE_CLASSES
        assert {"module", "headline", "legal", "portrait"} <= CORE_CLASSES

    def test_a_system_may_extend_it(self):
        assert "speaker-ring" in vocabulary_for(["speaker-ring"])

    def test_extensions_are_capped(self):
        with pytest.raises(VocabularyError) as e:
            vocabulary_for([f"x{i}" for i in range(MAX_CUSTOM_CLASSES + 1)])
        assert e.value.rule_id == "css.custom_class_limit"

    def test_a_custom_class_may_not_shadow_a_core_one(self):
        with pytest.raises(VocabularyError) as e:
            vocabulary_for(["headline"])
        assert e.value.rule_id == "css.custom_class_shadow"

    @pytest.mark.parametrize("name", ["9bad", "", "has space", "has_underscore"])
    def test_custom_class_names_are_constrained(self, name):
        with pytest.raises(VocabularyError):
            vocabulary_for([name])


class TestClassExtraction:
    def test_classes_used_walks_the_whole_tree(self):
        root = parse_authored('<div class="stack"><span class="badge chip"></span></div>')
        assert classes_used(root) == {"stack", "badge", "chip"}

    @pytest.mark.parametrize("selector,expected", [
        (".module", {"module"}),
        (".module > .module-label", {"module", "module-label"}),
        (".m + .m", {"m"}),
        (".module:first-child", {"module"}),
        ('[data-group="card"] .body', {"body"}),
    ])
    def test_classes_targeted(self, selector, expected):
        assert classes_targeted(selector) == expected


class TestReferenceTyping:
    """Types are derived from the reference, never taken from the model."""

    @pytest.mark.parametrize("ref,expected", [
        ("copy.headline", ElementType.HEADLINE),
        ("copy.subheadline", ElementType.SUBHEADLINE),
        ("copy.body", ElementType.BODY),
        ("copy.cta", ElementType.CTA),
        ("policy.disclaimer", ElementType.DISCLAIMER),
        ("facts.event.venue", ElementType.FACT),
        ("brand.logo.red", ElementType.LOGO),
        ("generated.qr", ElementType.QR),
        ("mountains.core_3", ElementType.MOUNTAINS),
        ("icon.shield", ElementType.IMAGE),
    ])
    def test_known_references(self, ref, expected):
        assert element_type_for(ref) is expected

    def test_photo_beats_the_broader_profile_prefix(self):
        # `profile.` would otherwise swallow this and type a portrait as a fact
        assert element_type_for("profile.photo.formal") is ElementType.AGENT_PHOTO
        assert element_type_for("profile.mobile") is ElementType.FACT

    @pytest.mark.parametrize("ref,expected", [
        ("content.speakers.1.label", ElementType.SUBHEADLINE),
        ("content.speakers.1.body", ElementType.BODY),
        ("content.benefits.0.icon", ElementType.IMAGE),
        ("content.stats.2.value", ElementType.FACT),
    ])
    def test_content_references(self, ref, expected):
        assert element_type_for(ref) is expected

    def test_module_labels_are_not_headlines(self):
        """Eight benefit labels must not compete with the headline in the ratio rules."""
        assert element_type_for("content.benefits.3.label") is not ElementType.HEADLINE

    def test_unknown_content_field(self):
        with pytest.raises(VocabularyError) as e:
            element_type_for("content.speakers.1.nickname")
        assert e.value.rule_id == "ref.unresolved"

    def test_unknown_namespace(self):
        with pytest.raises(VocabularyError) as e:
            element_type_for("secrets.api_key")
        assert e.value.rule_id == "ref.namespace"
