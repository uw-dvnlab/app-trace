from tracetool.annotate.base import AnnotatorBase


class ManualAnnotator(AnnotatorBase):
    name = "Manual Annotation"
    produces = None
    required_modalities = []  # none — user decides
    optional_modalities = []

    def annotate(self, signals):
        raise RuntimeError("Manual annotators do not run headlessly")
