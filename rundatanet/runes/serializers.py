from rest_framework import serializers

from .models import (
    Cross,
    CrossDefinition,
    CrossForm,
    ImageLink,
    Material,
    MaterialType,
    MetaInformation,
    MetaWithCrossesTextual,
    NameUsage,
    NormalisationNorse,
    NormalisationScandinavian,
    PersonalName,
    Reference,
    Signature,
    TranslationEnglish,
    TranslationSwedish,
    TransliteratedText,
)


class SignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signature
        fields = "__all__"


class CrossFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrossForm
        fields = "__all__"


class CrossDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrossDefinition
        fields = "__all__"


class CrossSerializer(serializers.ModelSerializer):
    forms = CrossDefinitionSerializer(many=True, read_only=True)

    class Meta:
        model = Cross
        fields = "__all__"


class MaterialTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialType
        fields = "__all__"


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = "__all__"


class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = ["text", "kind", "label"]


class MetaInformationSerializer(serializers.ModelSerializer):
    signature = serializers.StringRelatedField(many=False, read_only=True)
    crosses = serializers.SerializerMethodField()
    materialType = serializers.StringRelatedField(many=False, read_only=True)
    references = ReferenceSerializer(many=True, read_only=True)
    runic_texts = serializers.SerializerMethodField()

    class Meta:
        model = MetaInformation
        exclude = ["id"]

    def get_crosses(self, obj):
        try:
            meta_with_crosses = MetaWithCrossesTextual.objects.get(meta_id=obj.id)
            return meta_with_crosses.crosses_textual
        except MetaWithCrossesTextual.DoesNotExist:
            return ""

    def get_runic_texts(self, obj):
        result = []
        try:
            try:
                transliterated_text = TransliteratedText.objects.get(signature=obj.signature)
                result.append({"value": transliterated_text.value, "language_code": "run"})
            except:
                pass

            try:
                normalization_norse = NormalisationNorse.objects.get(signature=obj.signature)
                result.append({"value": normalization_norse.value, "language_code": "fvn"})
            except:
                pass

            try:
                normalization_scandinavian = NormalisationScandinavian.objects.get(signature=obj.signature)
                result.append({"value": normalization_scandinavian.value, "language_code": "rsv"})
            except:
                pass

            try:
                translation_english = TranslationEnglish.objects.get(signature=obj.signature)
                result.append({"value": translation_english.value, "language_code": "eng"})
            except:
                pass

            try:
                translation_swedish = TranslationSwedish.objects.get(signature=obj.signature)
                result.append({"value": translation_swedish.value, "language_code": "swe"})
            except:
                pass
        except:
            pass

        return result


class ImageLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageLink
        fields = "__all__"


class PersonalNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalName
        fields = "__all__"


class NameUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = NameUsage
        fields = "__all__"


class NormalisationNorseSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormalisationNorse
        fields = "__all__"


class NormalisationScandinavianSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormalisationScandinavian
        fields = "__all__"


class TransliteratedTextSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransliteratedText
        fields = "__all__"


class TranslationEnglishSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslationEnglish
        fields = "__all__"


class TranslationSwedishSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslationSwedish
        fields = "__all__"
