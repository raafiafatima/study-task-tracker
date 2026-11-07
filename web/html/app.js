(function () {
  "use strict";

  var form = document.getElementById("task-form");
  var input = document.getElementById("title");
  var addButton = document.getElementById("add-button");
  var formMessage = document.getElementById("form-message");
  var statusEl = document.getElementById("status");
  var retryButton = document.getElementById("retry-button");
  var list = document.getElementById("task-list");

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.className = isError ? "status error" : "status";
  }

  function render(tasks) {
    list.textContent = "";
    tasks.forEach(function (task) {
      var li = document.createElement("li");
      var title = document.createElement("span");
      title.className = "title";
      title.textContent = task.title; // textContent keeps user text inert
      var when = document.createElement("time");
      when.dateTime = task.created_at;
      when.textContent = new Date(task.created_at).toLocaleString();
      li.appendChild(title);
      li.appendChild(when);
      list.appendChild(li);
    });
  }

  // Resolves to parsed JSON, or rejects with an Error whose message is safe to show.
  function request(url, options) {
    return fetch(url, options).then(function (response) {
      return response.json().catch(function () { return null; }).then(function (body) {
        if (!response.ok) {
          var message = body && body.error ? body.error : "The server returned an error (" + response.status + ").";
          throw new Error(message);
        }
        return body;
      });
    });
  }

  function loadTasks() {
    retryButton.hidden = true;
    list.textContent = "";
    setStatus("Loading tasks…", false);
    return request("/api/tasks")
      .then(function (tasks) {
        render(tasks);
        setStatus(tasks.length ? "" : "No tasks yet. Add your first one above.", false);
      })
      .catch(function () {
        setStatus("Couldn't load your tasks. Check that the app is running, then try again.", true);
        retryButton.hidden = false;
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    formMessage.textContent = "";
    var title = input.value.trim();
    if (!title) {
      formMessage.textContent = "Enter a task before adding it.";
      input.focus();
      return;
    }
    addButton.disabled = true;
    request("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title })
    })
      .then(function () {
        input.value = "";
        return loadTasks();
      })
      .catch(function (err) {
        formMessage.textContent = err.message;
      })
      .then(function () {
        addButton.disabled = false;
        input.focus();
      });
  });

  retryButton.addEventListener("click", loadTasks);
  loadTasks();
})();
