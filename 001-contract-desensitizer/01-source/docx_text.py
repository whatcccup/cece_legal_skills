"""One OOXML text map for detection, rewriting and restoration."""
from pathlib import Path
import zipfile
from lxml import etree
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'

def paragraph_map(paragraph):
    chars, positions = [], []
    for node in paragraph.iter():
        if node is paragraph:
            continue
        owner = next((a for a in node.iterancestors() if a.tag == W+'p'), None)
        if owner is not paragraph:
            continue
        if node.tag in (W+'t', W+'delText'):
            for i, char in enumerate(node.text or ''):
                chars.append(char); positions.append((node, i))
        elif node.tag in (W+'tab', W+'br', W+'cr'):
            chars.append(' ' if node.tag == W+'tab' else '\n')
            positions.append((node, None))
    return ''.join(chars), positions

def replace_ranges(paragraph, replacements):
    text, positions = paragraph_map(paragraph)
    ordered = sorted(replacements, key=lambda r: r[0])
    end = 0
    for start, stop, replacement, expected in ordered:
        if start < end or not 0 <= start < stop <= len(text) or text[start:stop] != expected:
            raise RuntimeError('文字位置或原文不一致，已停止导出，请重新复核')
        end = stop
    pieces = {node: list(node.text or '') for node, offset in positions if offset is not None}
    remove = set()
    for start, stop, replacement, expected in reversed(ordered):
        spans = []
        for node, offset in positions[start:stop]:
            if offset is None:
                remove.add(node)
            elif spans and spans[-1][0] is node:
                spans[-1][2] = offset+1
            else:
                spans.append([node, offset, offset+1])
        if not spans:
            raise RuntimeError('替换范围没有可写文字')
        for i, (node, left, right) in enumerate(spans):
            pieces[node][left:right] = list(replacement if i == 0 else '')
    for node, value in pieces.items():
        node.text = ''.join(value)
        if node.text.startswith(' ') or node.text.endswith(' '): node.set(XML_SPACE, 'preserve')
    for node in remove: node.getparent().remove(node)
    return len(ordered)

class DocxText:
    def __init__(self, path):
        self.path = str(path)
        with zipfile.ZipFile(path) as archive:
            self.infos = archive.infolist()
            if len(self.infos) > 10000 or sum(i.file_size for i in self.infos) > 256*1024*1024:
                raise RuntimeError('Word 解压大小或部件数量超过安全上限')
            self.data = {i.filename: archive.read(i) for i in self.infos}
        self.trees, self.entries = {}, []
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        names = sorted(n for n in self.data if n.startswith('word/') and n.endswith('.xml'))
        if 'word/document.xml' in names:
            names.remove('word/document.xml'); names.insert(0, 'word/document.xml')
        for name in names:
            raw = self.data[name]
            if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:
                raise RuntimeError('Word 含不支持的 XML 实体声明')
            tree = etree.fromstring(raw, parser)
            self.trees[name] = tree
            for p in tree.iter(W+'p'):
                text, _ = paragraph_map(p)
                if text.strip(): self.entries.append((name, p))

    def sanitize_external(self):
        mapping_names = {n for n in self.data if n.startswith('customXml/') or n.endswith('.mapping.json')}
        unsupported = [n for n in self.data if n.startswith(('word/embeddings/', 'word/activeX/', 'word/afchunk')) or n.endswith(('vbaProject.bin', '.html', '.mht'))]
        # A mapping-only customXml directory is supported; other user data is not silently removed.
        if unsupported:
            raise RuntimeError('文件包含尚未检查的嵌入文件或自定义XML，请移除后再导出对外稿：'+unsupported[0])
        for n in mapping_names: self.data.pop(n)
        for n in list(self.data):
            if n.endswith('.rels') or n == '[Content_Types].xml':
                tree = etree.fromstring(self.data[n])
                for child in list(tree):
                    target = child.get('Target', '').lstrip('/')
                    part = child.get('PartName', '').lstrip('/')
                    if part in mapping_names or any(target.endswith(m) for m in mapping_names): tree.remove(child)
                self.data[n] = etree.tostring(tree, xml_declaration=True, encoding='UTF-8')
            elif n.startswith('docProps/') and n.endswith('.xml'):
                tree = etree.fromstring(self.data[n])
                for child in list(tree): tree.remove(child)
                self.data[n] = etree.tostring(tree, xml_declaration=True, encoding='UTF-8')
        for tree in self.trees.values():
            for node in list(tree.iter()):
                if node.tag == W+'dataBinding':
                    node.getparent().remove(node)
                    continue
                for attr in (W+'author', W+'initials'): node.attrib.pop(attr, None)

    def save(self, path):
        for name, tree in self.trees.items():
            self.data[name] = etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
        temp = str(path)+'.writing'
        try:
            with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as out:
                for info in self.infos:
                    if info.filename in self.data: out.writestr(info, self.data[info.filename])
            Path(temp).replace(path)
        finally:
            if Path(temp).exists(): Path(temp).unlink()
