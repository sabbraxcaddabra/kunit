from .mat_johnson_cook import SPEC as MAT_JC
from .eos_gruneisen import SPEC as EOS_GRUNEISEN
from .eos_jwl import SPEC as EOS_JWL
from .mat_high_explosive_burn import SPEC as MAT_HE_BURN

ALL_SPECS = [MAT_JC, EOS_GRUNEISEN, EOS_JWL, MAT_HE_BURN]
SPECS_BY_NAME = {s.name: s for s in ALL_SPECS}
