/* Ask AI - asynchronous question submission.
 * Uses the CSRF token from the cookie (Django's standard mechanism); CSRF
 * protection is NOT disabled server-side.
 */
(function () {
    "use strict";

    const form = document.getElementById("askForm");
    if (!form) {
        return; // No documents ready; nothing to wire up.
    }

    const documentSelect = document.getElementById("documentSelect");
    const questionInput = document.getElementById("questionInput");
    const askBtn = document.getElementById("askBtn");
    const askSpinner = document.getElementById("askSpinner");
    const askBtnText = document.getElementById("askBtnText");

    const placeholder = document.getElementById("answerPlaceholder");
    const answerCard = document.getElementById("answerCard");
    const answerText = document.getElementById("answerText");
    const answerStatus = document.getElementById("answerStatus");
    const mockNotice = document.getElementById("mockNotice");
    const sourcesSection = document.getElementById("sourcesSection");
    const sourcesList = document.getElementById("sourcesList");
    const usageBadge = document.getElementById("usageBadge");

    // Pre-select a document if ?document=<id> was passed.
    const params = new URLSearchParams(window.location.search);
    const preselect = params.get("document");
    if (preselect) {
        documentSelect.value = preselect;
    }

    function getCookie(name) {
        const match = document.cookie.match(
            "(^|;)\\s*" + name + "\\s*=\\s*([^;]+)"
        );
        return match ? decodeURIComponent(match.pop()) : "";
    }

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    function setLoading(isLoading) {
        askBtn.disabled = isLoading;
        askSpinner.classList.toggle("d-none", !isLoading);
        askBtnText.classList.toggle("d-none", isLoading);
    }

    function badge(status) {
        const map = {
            success: ["Successful", "text-bg-success"],
            unsupported: ["Unsupported", "text-bg-secondary"],
            failed: ["Failed", "text-bg-danger"],
        };
        const entry = map[status] || ["", "text-bg-light"];
        return '<span class="badge ' + entry[1] + '">' + entry[0] + "</span>";
    }

    function renderSources(sources, documentName) {
        sourcesList.innerHTML = "";
        if (!sources || sources.length === 0) {
            sourcesSection.classList.add("d-none");
            return;
        }
        sources.forEach(function (source) {
            const wrapper = document.createElement("div");
            wrapper.className = "source-item";
            const label = source.label
                ? " — " + escapeHtml(source.label)
                : "";
            const score =
                source.score != null
                    ? '<small class="text-muted">relevance ' +
                      escapeHtml(source.score) +
                      "</small>"
                    : "";
            const snippet = source.snippet
                ? '<p class="text-muted small mb-0 mt-1">' +
                  escapeHtml(source.snippet) +
                  "</p>"
                : "";
            wrapper.innerHTML =
                '<div class="d-flex justify-content-between">' +
                "<strong>" +
                escapeHtml(documentName) +
                label +
                "</strong>" +
                score +
                "</div>" +
                snippet;
            sourcesList.appendChild(wrapper);
        });
        sourcesSection.classList.remove("d-none");
    }

    function showAnswer(data, documentName) {
        placeholder.classList.add("d-none");
        answerCard.classList.remove("d-none");
        answerStatus.innerHTML = badge(data.status);
        mockNotice.classList.toggle(
            "d-none",
            !(data.is_mock && data.supported)
        );
        answerText.textContent = data.answer;
        renderSources(data.sources, documentName);
        if (data.usage && usageBadge) {
            usageBadge.textContent =
                data.usage.remaining + "/" + data.usage.limit +
                " questions left today";
        }
    }

    function showError(message) {
        placeholder.classList.add("d-none");
        answerCard.classList.remove("d-none");
        answerStatus.innerHTML = badge("failed");
        mockNotice.classList.add("d-none");
        answerText.textContent = message;
        sourcesSection.classList.add("d-none");
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        const documentId = documentSelect.value;
        const question = questionInput.value.trim();
        if (!documentId || !question) {
            return;
        }
        const documentName =
            documentSelect.options[documentSelect.selectedIndex].text;

        setLoading(true);
        fetch(window.DOCUMIND_ASK_URL || "/api/ask/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
                document_id: documentId,
                question: question,
            }),
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (result.ok) {
                    showAnswer(result.data, documentName);
                } else {
                    showError(
                        result.data.error ||
                            "Something went wrong. Please try again."
                    );
                }
            })
            .catch(function () {
                showError("Network error. Please check your connection.");
            })
            .finally(function () {
                setLoading(false);
            });
    });
})();
