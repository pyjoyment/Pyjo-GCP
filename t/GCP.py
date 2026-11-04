import Pyjo.GCP

from Pyjo.Test import *

import importlib.metadata
import re


# The package of the distribution, in the namespace Pyjo of Pyjoyment, which extend_path keeps open

with subtest('Namespace'):
    import Pyjo.URL

    like_ok(Pyjo.GCP.__file__, r'Pyjo[\\/]GCP[\\/]__init__\.py$', 'package of the distribution')
    ok(Pyjo.URL.new('http://example.com').host == 'example.com', 'modules of Pyjoyment')

with subtest('Version'):
    like_ok(Pyjo.GCP.__version__, re.compile(r'^\d+\.\d+\.\d+'), 'version of the distribution')
    is_ok(Pyjo.GCP.__version__, importlib.metadata.version('Pyjo-GCP'), 'version of the metadata')

done_testing()
