"""Bounded extraction metadata cache owned by one browser session, never shared globally."""
from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
from time import monotonic


class DocumentCache:
    def __init__(self,max_entries=32,ttl=1800,version='local-v7'):
        self.max_entries=max_entries
        self.ttl=ttl
        self.version=version
        self.entries=OrderedDict()
        self.hits=0
        self.misses=0

    def read(self,parser,documents,compute):
        now=monotonic()
        for key,(created,_) in list(self.entries.items()):
            if now-created>=self.ttl:self.entries.pop(key)
        # Keep names AND bytes in the identity: returned evidence must name the
        # actual current upload. No uploaded bytes or final comparisons are cached.
        key=(self.version,parser,tuple((name,sha256(raw).hexdigest()) for name,raw in documents))
        if key in self.entries:
            self.hits+=1
            self.entries.move_to_end(key)
            return deepcopy(self.entries[key][1])
        self.misses+=1
        value=compute()  # Failures are not cached.
        self.entries[key]=(now,deepcopy(value))
        while len(self.entries)>self.max_entries:self.entries.popitem(last=False)
        return value


def cached_parse(cache,parser,documents,compute):
    return compute() if cache is None else cache.read(parser,documents,compute)
