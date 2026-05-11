from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Specification:
    """Composable predicate over domain objects.

    Subclasses are concrete leaf specs (e.g. `ProfileIsVisible`). Compose
    them with `&` to express conjunctions; OR / NOT are not implemented
    because we don't need them yet.

    Specs are translated to SQL by an infrastructure-side applier
    (`DiscoverySpecApplier`) — domain code stays SQL-free.
    """

    def __and__(self, other: "Specification") -> "Specification":
        # Flatten nested AndSpec to keep the tree shallow.
        left = self.specs if isinstance(self, AndSpec) else (self,)
        right = other.specs if isinstance(other, AndSpec) else (other,)
        return AndSpec(specs=left + right)


@dataclass(frozen=True, slots=True)
class AndSpec(Specification):
    specs: tuple[Specification, ...] = field(default_factory=tuple)
