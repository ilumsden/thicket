from .frame import Frame


class Node:
    def __init__(self, frame: Frame, hnid=-1, depth=-1):
        self.frame = frame
        self._hatchet_nid = hnid
        self._depth = depth

    def __hash__(self):
        return self._hatchet_nid

    def __eq__(self, other):
        return self._hatchet_nid == other._hatchet_nid

    def __lt__(self, other):
        return self._hatchet_nid < other._hatchet_nid

    def __gt__(self, other):
        return self._hatchet_nid > other._hatchet_nid

    def __str__(self):
        """Returns a string representation of the node."""
        return str(self.frame)

    def copy(self):
        """Copy this node without preserving parents or children."""
        return Node(frame_obj=self.frame.copy())

    def __repr__(self):
        return "Node({%s})" % ", ".join(
            "%s: %s" % (repr(k), repr(v)) for k, v in sorted(self.frame.attrs.items())
        )
