from django.db import models


# Create your models here.
class Signature(models.Model):
    signature_text = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        related_name="children",
        on_delete=models.CASCADE,
    )
    # meta = models.ForeignKey('MetaInformation',
    #     on_delete = models.CASCADE,
    #     blank = True,
    #     null = True,
    #     related_name = "signature",
    #     )

    def __str__(self):
        return self.signature_text

    class Meta:
        db_table = "signatures"
        indexes = [
            models.Index(fields=["signature_text"]),
        ]


class CrossForm(models.Model):
    """CrossForm is a building block of crosses. Each cross consists of a list of CrossForms"""

    name = models.CharField(max_length=200)
    group_id = models.PositiveIntegerField(default=0, blank=False, null=False)

    def __str__(self):
        return "{} in group {}".format(self.name, self.group_id)

    class Meta:
        db_table = "cross_forms"


class CrossDefinition(models.Model):
    """CrossDefinition is used to construct a list of CrossForm objects"""

    cross = models.ForeignKey("Cross", blank=False, null=False, on_delete=models.CASCADE, related_name="forms")
    form = models.ForeignKey(CrossForm, on_delete=models.CASCADE, blank=False, null=False)
    is_certain = models.BooleanField(default=True)

    class Meta:
        db_table = "cross_definitions"


class Cross(models.Model):
    """Cross defines one particular cross"""

    # Cross contains a link to meta information and accessible from
    # meta information via <meta>.crosses. Each meta can have several crosses.
    # Each cross is a list of CrossDefinition objects.
    meta = models.ForeignKey(
        "MetaInformation", on_delete=models.CASCADE, blank=False, null=False, related_name="crosses"
    )

    def __str__(self):
        res = []
        res.append("{} => ".format(self.id))
        for i, crossDefinition in enumerate(self.forms.all()):
            if i:
                res.append(", ".format(crossDefinition.form.name))
            res.append(crossDefinition.form.name)

        return "".join(res)

    class Meta:
        db_table = "crosses"


class Reference(models.Model):
    """A single bibliographic reference entry.

    Text references are plain bibliographic strings, e.g. 'SRI 1 plansch IV fig. 3'.
    Link references are URLs with a human-readable label, e.g.
    label='Swedish Runic Bibliography'.
    In the flat DB view, links are encoded as '<label>:::<url>' so the frontend and
    export layer can recover the display name without pattern-matching on the URL.
    """

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        LINK = "link", "Link"

    text = models.CharField(max_length=1500, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TEXT)
    # Human-readable display name; only meaningful when kind=LINK.
    label = models.CharField(max_length=300, blank=True)

    def __str__(self):
        if self.kind == self.Kind.LINK and self.label:
            return f"{self.label}: {self.text}"
        return self.text

    class Meta:
        db_table = "references"
        ordering = ["text"]


class MaterialType(models.Model):
    name = models.TextField(blank=False, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "material_types"


class Material(models.Model):
    type = models.ForeignKey(MaterialType, on_delete=models.CASCADE)
    name = models.TextField(blank=True, null=False, unique=False)


# default: blank=False, null=False
class MetaInformation(models.Model):
    # Plats
    found_location = models.TextField()
    # Socken
    parish = models.TextField(blank=True)
    # Härad
    district = models.TextField(blank=True)
    # Kommun
    municipality = models.TextField(blank=True)
    # Placering
    current_location = models.TextField(blank=True)
    # Koordinater
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    # Urspr. plats?
    original_site = models.TextField(blank=True)
    # Nuv. koord.
    present_latitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    present_longitude = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    # Sockenkod/Fornlämningsnr.
    parish_code = models.TextField(blank=True)
    # Runtyper
    rune_type = models.TextField(blank=True)

    # Cross is defined externally

    # Period/Datering
    dating = models.TextField(blank=True)
    # more accurate dating with year from and year to
    year_from = models.PositiveIntegerField(blank=True, null=True)
    year_to = models.PositiveIntegerField(blank=True, null=True)

    # Stilgruppering
    style = models.TextField(blank=True)
    # Ristare
    carver = models.TextField(blank=True)
    # Materialtyp
    materialType = models.ForeignKey(MaterialType, on_delete=models.CASCADE, blank=True, null=True)
    # Material
    material = models.TextField(blank=True)

    # Föremål
    objectInfo = models.TextField(blank=True)

    # Övrigt
    additional = models.TextField(blank=True)

    # alternative signature is managed externally

    # Referens (legacy plain-text field, kept during migration)
    reference = models.TextField(blank=True)
    # Normalised references (M2M)
    references = models.ManyToManyField(Reference, blank=True, related_name="meta_informations")

    # Bildlänk is managed externally

    # not in original Excel:
    lost = models.BooleanField(default=False)
    new_reading = models.BooleanField(default=False)
    # If inscription is purely ornamental
    ornamental = models.BooleanField(default=False)
    # If inscription is recent (Santida)
    recent = models.BooleanField(default=False)

    signature = models.OneToOneField(Signature, on_delete=models.CASCADE, related_name="meta")

    def __str__(self):
        return "Meta for {}".format(self.signature.signature_text)

    class Meta:
        db_table = "meta_information"
        indexes = [
            models.Index(fields=["found_location"]),
            models.Index(fields=["parish"]),
            models.Index(fields=["municipality"]),
            models.Index(fields=["current_location"]),
            models.Index(fields=["style"]),
        ]


# class SignatureMetaRelation(models.Model):
#     signature = models.OneToOneField(Signature,
#         on_delete = models.CASCADE,
#         related_name = 'meta'
#         )
#     meta = models.OneToOneField(MetaInformation,
#         on_delete = models.CASCADE,
#         related_name = 'signature'
#         )


class ImageLink(models.Model):
    meta = models.ForeignKey(MetaInformation, on_delete=models.CASCADE, related_name="images")
    link_url = models.URLField()
    direct_url = models.URLField(blank=True)


class PersonalName(models.Model):
    """Storage of personal names from all text files."""

    value = models.CharField(max_length=60, unique=True, blank=False, null=False)
    """str: Personal name value"""

    def __str__(self):
        return "{}".format(self.value)

    class Meta:
        indexes = [models.Index(fields=["value"])]


class NameUsage(models.Model):
    """Information about how a personal name is used in text."""

    name = models.ForeignKey(PersonalName, on_delete=models.CASCADE, related_name="usage")

    word_index = models.PositiveIntegerField(default=0, blank=False, null=False)
    """int: Index of the word inside the text, e.g. 5 means this name is
         the fith word in the text."""

    signature = models.ForeignKey(Signature, on_delete=models.CASCADE, related_name="personal_names")

    def __str__(self):
        return "Signature {}, name {}, word index {}".format(
            self.signature.signature_text, self.name.value, self.word_index
        )


class TextModel(models.Model):
    """Base class for all text models

    Text models are used to store text data in a way that is suitable for search.
    They are simple models with two fields: value and search_value. The first one
    stores value which is displayed to user, the second one stores stripped version of the value
    suitable for running text search on.
    """

    # original value which can be displayed to user
    value = models.TextField(blank=True, null=False)
    # stripped version of value suitable for search
    search_value = models.TextField(blank=True, null=False)

    def __str__(self):
        return "{}: {}".format(self.signature.signature_text, self.value)

    class Meta:
        abstract = True


class NormalisationNorse(TextModel):
    signature = models.OneToOneField(
        Signature,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="normalisation_norse",
    )

    class Meta:
        db_table = "normalisation_norse"
        indexes = [
            models.Index(fields=["search_value"]),
        ]


class NormalisationScandinavian(TextModel):
    signature = models.OneToOneField(
        Signature,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="normalisation_scandinavian",
    )

    class Meta:
        db_table = "normalisation_scandinavian"
        indexes = [
            models.Index(fields=["search_value"]),
        ]


class TransliteratedText(TextModel):
    signature = models.OneToOneField(
        Signature,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="transliteration",
    )

    class Meta:
        db_table = "transliterated_text"
        indexes = [
            models.Index(fields=["search_value"]),
        ]


class TranslationEnglish(TextModel):
    signature = models.OneToOneField(
        Signature,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="translation_english",
    )

    class Meta:
        db_table = "translation_english"
        indexes = [
            models.Index(fields=["search_value"]),
        ]


class TranslationSwedish(TextModel):
    signature = models.OneToOneField(
        Signature,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="translation_swedish",
    )

    class Meta:
        db_table = "translation_swedish"
        indexes = [
            models.Index(fields=["search_value"]),
        ]


class MetaWithCrossesTextual(models.Model):
    # This is a view in the DB

    meta_id = models.IntegerField(primary_key=True)
    crosses_textual = models.TextField()

    class Meta:
        managed = False  # No migrations will be created for this model
        db_table = "meta_with_crosses_textual"
