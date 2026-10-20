"""Small standard-library HTML text reader for presentation assertions."""
from html.parser import HTMLParser


def element_texts(markup, tag, *, cls=None):
    """Read element text through nested markup, preserving document order."""
    class Elements(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.elements = []

        def handle_starttag(self, name, attrs):
            if name != tag:
                return
            for element in self.elements:
                if element['depth']:
                    element['depth'] += 1
            if cls is None or cls in dict(attrs).get('class', '').split():
                self.elements.append(dict(depth=1, text=[]))

        def handle_endtag(self, name):
            if name == tag:
                for element in self.elements:
                    if element['depth']:
                        element['depth'] -= 1

        def handle_data(self, value):
            for element in self.elements:
                if element['depth']:
                    element['text'].append(value)

    parser = Elements()
    parser.feed(markup.decode() if isinstance(markup, bytes) else markup)
    return [''.join(element['text']) for element in parser.elements]
