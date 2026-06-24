// File chosen 
function onFileChosen() {
    const fileInput = document.getElementById("pdfFile");
    const label = document.getElementById("fileLabel");
    const uploadBtn = document.getElementById("uploadBtn");

    if (fileInput.files.length) {
        label.textContent = fileInput.files[0].name;
        uploadBtn.disabled = false;
    }
}

//Upload pdf
async function uploadPDF() {
    const fileInput = document.getElementById("pdfFile");

    if (!fileInput.files.length) {
        alert("Select a PDF first");
        return;
    }

    const formData = new FormData();
    formData.append("pdf", fileInput.files[0]);

    // Show progress bar, disable button
    setUploadUI("loading");

    try {
        const response = await fetch("/upload", { method: "POST", body: formData });
        const result = await response.json();

        if (result.status === "success") {
            setUploadUI("done", `✅ ${result.message} — ${result.stats.texts} text chunks, ${result.stats.tables} tables, ${result.stats.images} images indexed.`);
            enableChat();
        } else {
            setUploadUI("error", `❌ ${result.message}`);
        }
    } catch (e) {
        setUploadUI("error", "❌ Upload failed. Check the server.");
    }
}

function setUploadUI(state, message) {
    const progressWrap = document.getElementById("progressWrap");
    const progressFill = document.getElementById("progressFill");
    const progressLabel = document.getElementById("progressLabel");
    const status = document.getElementById("status");
    const uploadBtn = document.getElementById("uploadBtn");

    if (state === "loading") {
        progressWrap.classList.remove("hidden");
        progressFill.classList.add("indeterminate");
        progressLabel.textContent = "Processing PDF — extracting text, tables & images. This may take a few minutes…";
        uploadBtn.disabled = true;
        uploadBtn.textContent = "Processing…";
        status.textContent = "";
    } else {
        progressWrap.classList.add("hidden");
        progressFill.classList.remove("indeterminate");
        uploadBtn.textContent = "Upload PDF";
        status.textContent = message || "";
        status.className = state === "done" ? "status-ok" : "status-err";
    }
}

function enableChat() {
    document.getElementById("question").disabled = false;
    document.getElementById("sendBtn").disabled = false;
    document.getElementById("chatBox").innerHTML = "";
}

// questions 
async function askQuestion() {
    const questionBox = document.getElementById("question");
    const question = questionBox.value.trim();
    if (!question) return;

    const chatBox = document.getElementById("chatBox");
    const sendBtn = document.getElementById("sendBtn");
    const queryHint = document.getElementById("queryHint");

    // Show user message
    chatBox.innerHTML += `<div class="user">${escapeHtml(question)}</div>`;
    questionBox.value = "";

    // Show typing indicator + hint
    const typingId = "typing-" + Date.now();
    chatBox.innerHTML += `<div class="bot typing" id="${typingId}">
        <span></span><span></span><span></span>
    </div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    sendBtn.disabled = true;
    questionBox.disabled = true;
    queryHint.classList.remove("hidden");

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        });

        const result = await response.json();
        const answer = result.answer || result.message || "No answer returned.";

        // Replace typing indicator with answer
        document.getElementById(typingId).outerHTML =
            `<div class="bot">${escapeHtml(answer)}</div>`;
    } catch (e) {
        document.getElementById(typingId).outerHTML =
            `<div class="bot error">❌ Request failed. Is the server running?</div>`;
    }

    sendBtn.disabled = false;
    questionBox.disabled = false;
    queryHint.classList.add("hidden");
    chatBox.scrollTop = chatBox.scrollHeight;
    questionBox.focus();
}

function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}