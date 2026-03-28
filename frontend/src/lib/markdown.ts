import DOMPurify from 'dompurify';
import { Marked } from 'marked';

const marked = new Marked({
	breaks: true,
	gfm: true
});

export function renderMarkdown(src: string): string {
	const raw = marked.parse(src);
	if (typeof raw !== 'string') return '';
	return DOMPurify.sanitize(raw);
}
