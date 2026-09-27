import test from 'node:test';
import assert from 'node:assert/strict';
import { releaseNotesMarkdown, renderUpdateMarkdown } from '../src/update-markdown.js';

class NodeStub {
  constructor(tagName, text = '') { this.tagName = tagName.toUpperCase(); this.textContent = text; this.children = []; this.attributes = {}; this.hidden = false; }
  append(node) { this.children.push(node); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = value; }
  get childElementCount() { return this.children.filter((child) => child.tagName !== '#TEXT').length; }
}

test('legacy release note arrays are converted to Markdown without showing source backticks', () => {
  assert.equal(releaseNotesMarkdown('', ['Adds `Cirava.exe`'], '1.1.4'), "## What's new in 1.1.4\n\n- Adds `Cirava.exe`");
});

test('update Markdown renders headings, lists, emphasis and safe links as DOM nodes', () => {
  const priorDocument = globalThis.document;
  globalThis.document = {
    createElement: (tag) => new NodeStub(tag),
    createTextNode: (text) => new NodeStub('#text', text),
  };
  try {
    const container = new NodeStub('div');
    renderUpdateMarkdown(container, '# 1.1.4\n\n## Highlights\n\n- Adds **resumable uploads** and `Cirava.exe`.\n- Read [the guide](https://example.com/wiki).\n\n<script>alert(1)</script>', '1.1.4');
    assert.equal(container.children.some((node) => node.tagName === 'H1'), false, 'the repeated release-version title is removed');
    assert.equal(container.children.some((node) => node.tagName === 'H3'), true);
    const list = container.children.find((node) => node.tagName === 'UL');
    assert.ok(list);
    assert.ok(list.children[0].children.some((node) => node.tagName === 'STRONG'));
    assert.ok(list.children[0].children.some((node) => node.tagName === 'CODE'));
    const link = list.children[1].children.find((node) => node.tagName === 'A');
    assert.equal(link.href, 'https://example.com/wiki');
    assert.equal(link.rel, 'noopener noreferrer');
    const scriptText = container.children.find((node) => node.tagName === 'P');
    assert.ok(scriptText.children.every((node) => node.tagName !== 'SCRIPT'), 'HTML-looking release text remains ordinary text');
    assert.equal(container.hidden, false);
  } finally {
    if (priorDocument === undefined) delete globalThis.document;
    else globalThis.document = priorDocument;
  }
});

test('unsafe non-HTTPS Markdown links are left as plain text', () => {
  const priorDocument = globalThis.document;
  globalThis.document = {
    createElement: (tag) => new NodeStub(tag),
    createTextNode: (text) => new NodeStub('#text', text),
  };
  try {
    const container = new NodeStub('div');
    renderUpdateMarkdown(container, '[bad](javascript:alert(1))');
    assert.equal(container.children[0].tagName, 'P');
    assert.equal(container.children[0].children.some((node) => node.tagName === 'A'), false);
  } finally {
    if (priorDocument === undefined) delete globalThis.document;
    else globalThis.document = priorDocument;
  }
});
