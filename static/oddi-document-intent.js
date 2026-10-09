(function attachOddiDocumentIntent() {
    function normalizePrompt(text) {
        return String(text || "").toLowerCase().replace(/[’']/g, "'");
    }

    function isEducationalQuestion(text) {
        const value = normalizePrompt(text);
        const question = /^(explain|what (?:is|are|formats|file types|options)|how (?:do|can|should|to)|why|when|where|who|tell me how|tell me about)\b/.test(value);
        const asksAboutFormats = /^what (?:formats|file types|options)\b/.test(value);
        const directOutputRequest = /\b(?:create|write|generate|prepare|draft|compose|make|give|provide|send|download|export|save|convert|format|turn)\b.{0,50}\b(?:me|my|this|it|that|one|a downloadable)\b/.test(value) ||
            (!asksAboutFormats && /\b(?:as|into)\s+(?:a\s+)?(?:downloadable\s+)?(?:pdf|docx?|word document|text file|markdown|html|png)\b/.test(value));
        return question && !directOutputRequest;
    }

    function isDocumentGenerationIntent(text) {
        const value = normalizePrompt(text);
        const createIntent = /\b(create|write|generate|prepare|draft|compose|make|build|produce|format|tailor|rewrite|turn|convert|provide|give|download|export|bana(?:o|ye)?|taiyar|likh(?:na|o|iye)?)\b/.test(value);
        const tableArtifact = /\btable\b/.test(value) && /\b(data|spreadsheet|excel|download|file|document|csv|xlsx)\b/.test(value);
        const artifact = /\b(resume|curriculum vitae|cv|cover letter|essay|letter|application|report|assignment|notes|article|blog|documentation|docs|proposal|invoice|document|file|spreadsheet|workbook|pdf|docx?|html|markdown|\.md|png|downloadable|long[- ]form|multi[- ]page)\b/.test(value) || tableArtifact;
        const explicitExport = /\b(download|downloadable|export|save|provide|give me|get me)\b.{0,70}\b(pdf|docx?|word|txt|text file|markdown|html|png|file|document)\b/.test(value) ||
            /\b(?:as|into)\s+(?:a\s+)?(?:downloadable\s+)?(?:pdf|docx?|word document|text file|markdown|html|png|file|document)\b/.test(value);
        const substantial = /\b(long|long-form|comprehensive|detailed|10[- ]page|multi[- ]page|large|huge)\b/.test(value) && createIntent;
        if (isEducationalQuestion(value)) return false;
        return explicitExport || (createIntent && artifact) || (substantial && /\b(content|text|article|report|essay|proposal|document|assignment|notes)\b/.test(value));
    }

    function documentTitleFromPrompt(text) {
        const value = String(text || "");
        const knownTitles = [
            [/\bcover letter\b/i, "Cover Letter"],
            [/\bresume\b|\bcv\b|curriculum vitae/i, "Resume"],
            [/\bbusiness proposal\b/i, "Business Proposal"],
            [/\bproposal\b/i, "Proposal"],
            [/\binvoice\b/i, "Invoice"],
            [/\breport\b/i, "Report"],
            [/\bassignment\b/i, "Assignment"],
            [/\bessay\b/i, "Essay"],
            [/\barticle\b/i, "Article"],
            [/\bblog\b/i, "Blog Post"],
            [/\bnotes\b/i, "Notes"],
            [/\bdocumentation\b|\bdocs\b/i, "Documentation"],
            [/\bapplication\b/i, "Application"],
            [/\bletter\b/i, "Letter"],
            [/\bspreadsheet\b|\bworkbook\b/i, "Spreadsheet"],
            [/\bdocument\b|\bfile\b/i, "Document"]
        ];
        return knownTitles.find(([pattern]) => pattern.test(value))?.[1] || "Document Draft";
    }

    function isDocumentExportFollowup(text) {
        const value = normalizePrompt(text);
        const asksExport = /\b(download|export|save|give|provide|get|send|convert|format|turn)\b.{0,70}\b(pdf|docx?|word|txt|text file|markdown|html|png|file)\b/.test(value) ||
            /\b(?:as|into)\s+(?:a\s+)?(?:pdf|docx?|word|txt|text file|markdown|html|png)\b/.test(value);
        return asksExport && !/\b(?:create|write|generate|prepare|draft|compose|build|produce)\b/.test(value);
    }

    function documentFormatFromPrompt(text) {
        const value = normalizePrompt(text);
        if (/\b(docx?|word)\b/.test(value)) return "docx";
        if (/\b(html|web page)\b/.test(value)) return "html";
        if (/\b(markdown|\.md)\b/.test(value)) return "md";
        if (/\b(txt|text file|plain text)\b/.test(value)) return "txt";
        if (/\b(png|image)\b/.test(value)) return "png";
        return "pdf";
    }

    function shouldIncludeDocumentInModelHistory(text) {
        const value = normalizePrompt(text);
        return /\b(edit|revise|rewrite|update|shorten|expand|tailor|improve|correct|proofread|adjust|change|modify|add|remove|replace|make)\b.{0,90}\b(document|resume|cv|letter|report|proposal|essay|it|this|that)\b/.test(value) ||
            /\b(?:it|this|that)\b.{0,35}\b(?:shorter|longer|clearer|more concise|more detailed|updated|revised)\b/.test(value);
    }

    window.OddiDocumentIntent = {
        isDocumentGenerationIntent,
        isEducationalQuestion,
        documentTitleFromPrompt,
        isDocumentExportFollowup,
        documentFormatFromPrompt,
        shouldIncludeDocumentInModelHistory
    };
})();
