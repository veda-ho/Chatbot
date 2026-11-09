const sendButton =
    document.getElementById("send-button");

const userInput =
    document.getElementById("user-input");

const chatBox =
    document.getElementById("chat-box");

const micButton =
    document.getElementById("mic-button");


// "student" or "staff", chosen on the home page
const userRole =
    document.body.dataset.role || "student";


// ========================================
// CHAT SESSION
// Everything the bot remembers in this sitting:
//   history: every message so far (sent to Gemini)
//   context: details like university, date, school, cGPA
// Saved in the browser tab, so a refresh keeps the chat.
// Going back to the home page starts a new chat.
// ========================================

const STORAGE_KEY = "exchangebot-chat";

let session = {
    role: userRole,
    history: [],
    context: {}
};


function saveSession() {

    try {
        sessionStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(session)
        );
    }

    catch (error) {
        // storage blocked: the chat still works, it just won't survive a refresh
    }
}


function loadSession() {

    try {

        const saved = JSON.parse(
            sessionStorage.getItem(STORAGE_KEY)
        );

        // only reuse a saved chat for the same role
        if (saved && saved.role === userRole) {
            session = saved;
        }
    }

    catch (error) {
        // nothing saved, or storage blocked: start fresh
    }
}


// ========================================
// SHOW MESSAGES
// ========================================

function addMessage(text, who, buttons) {

    const bubble =
        document.createElement("div");

    bubble.classList.add(
        "message",
        who === "user" ? "user-message" : "bot-message"
    );

    bubble.textContent = text;


    // Buttons under the answer:
    //   "Search on Trip.com" (opens Trip.com with the search filled in)
    //   "Email the GEM Explorer team" (opens an email with the question filled in)
    if (buttons && buttons.length) {

        const row =
            document.createElement("div");

        row.classList.add("button-row");

        for (const button of buttons) {

            const link =
                document.createElement("a");

            link.classList.add(
                "chat-button",
                button.href.startsWith("mailto:") ? "handoff-button" : "trip-button"
            );

            link.href = button.href;
            link.target = "_blank";
            link.rel = "noopener";
            link.textContent = button.label;

            row.appendChild(link);
        }

        bubble.appendChild(row);
    }

    chatBox.appendChild(bubble);

    chatBox.scrollTop =
        chatBox.scrollHeight;

    return bubble;
}


function addBotMessage(text, buttons) {

    return addMessage(text, "bot", buttons);
}


// Put back the earlier messages after a refresh
function restoreChat() {

    loadSession();

    for (const turn of session.history) {
        addMessage(turn.text, turn.role, turn.buttons);
    }
}


// ========================================
// SEND MESSAGE
// ========================================

async function sendMessage() {

    const message =
        userInput.value.trim();


    if (message === "") {
        return;
    }


    // Show the user's message and clear the box
    addMessage(message, "user");

    userInput.value = "";


    // Temporary loading message
    const loadingMessage =
        addBotMessage("Thinking...");


    // Stop waiting after 45 seconds so "Thinking..." never hangs forever
    const controller = new AbortController();

    const timer = setTimeout(
        () => controller.abort(),
        45000
    );


    try {

        const response = await fetch(
            "/chat",
            {
                method: "POST",

                signal: controller.signal,

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    message: message,
                    user_type: userRole,
                    context: session.context,
                    history: session.history
                })
            }
        );


        const data =
            await response.json();

        clearTimeout(timer);


        loadingMessage.remove();

        addBotMessage(data.reply, data.buttons);


        // Remember this exchange for the rest of the sitting
        session.history.push(
            { role: "user", text: message },
            { role: "bot", text: data.reply, buttons: data.buttons }
        );

        if (data.context) {
            session.context = data.context;
        }

        saveSession();

    }

    catch (error) {

        clearTimeout(timer);

        console.error(
            "Chat error:",
            error
        );

        loadingMessage.remove();

        if (error.name === "AbortError") {

            addBotMessage(
                "⏳ That took too long. Please send your question again."
            );

        }

        else {

            addBotMessage(
                "Sorry, something went wrong. Check the terminal for the error."
            );

        }

    }
}


// ========================================
// SEND BUTTON AND ENTER KEY
// ========================================

sendButton.addEventListener(
    "click",
    sendMessage
);


userInput.addEventListener(
    "keypress",
    function(event) {

        if (event.key === "Enter") {

            sendMessage();

        }

    }
);


// ========================================
// MIC BUTTON (SPEECH TO TEXT)
// Uses the browser's built-in speech recognition (Chrome / Edge)
// ========================================

const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;


if (SpeechRecognition) {

    const recognition =
        new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.interimResults = false;


    micButton.addEventListener(
        "click",
        function() {

            micButton.classList.add("listening");
            recognition.start();

        }
    );


    // Put what the user said into the box, then send it
    recognition.addEventListener(
        "result",
        function(event) {

            userInput.value =
                event.results[0][0].transcript;

            sendMessage();

        }
    );


    recognition.addEventListener(
        "end",
        function() {

            micButton.classList.remove("listening");

        }
    );


    recognition.addEventListener(
        "error",
        function(event) {

            console.error("Speech error:", event.error);
            micButton.classList.remove("listening");

        }
    );

}

else {

    micButton.title =
        "Voice input works in Chrome or Edge";

    micButton.addEventListener(
        "click",
        function() {

            addBotMessage(
                "Voice input isn't supported in this browser. Try Chrome or Edge."
            );

        }
    );

}


// ========================================
// START: bring back this sitting's chat, if any
// ========================================

restoreChat();
