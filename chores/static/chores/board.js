(function () {
  "use strict";

  function csrfToken() {
    const cookie = document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  }

  function actionFor(targetName, card) {
    const assignmentStatus = card.dataset.assignmentStatus;
    const assignedToCurrent = card.dataset.assignedToCurrent === "true";

    if (targetName === "mine" && assignmentStatus === "unassigned") {
      return { url: card.dataset.claimUrl, confirmation: false };
    }
    if (
      targetName === "open" &&
      assignmentStatus === "accepted" &&
      assignedToCurrent
    ) {
      return { url: card.dataset.unclaimUrl, confirmation: false };
    }
    if (targetName === "completed") {
      return {
        url: card.dataset.completeUrl,
        confirmation: card.dataset.completionNeedsConfirmation === "true",
      };
    }
    return null;
  }

  async function postAction(action) {
    const body = new URLSearchParams();
    if (action.confirmation) {
      const confirmed = window.confirm(
        "This chore is assigned to someone else. Mark it complete anyway?",
      );
      if (!confirmed) return;
      body.set("confirm", "yes");
    }

    const response = await fetch(action.url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      body: body.toString(),
      credentials: "same-origin",
    });

    if (!response.ok) {
      window.alert("That chore could not be moved. Refresh and try again.");
      return;
    }
    window.location.assign(response.url);
  }

  document.addEventListener("DOMContentLoaded", function () {
    let draggedCard = null;

    document
      .querySelectorAll('article[draggable="true"]')
      .forEach(function (card) {
        card.addEventListener("dragstart", function (event) {
          draggedCard = card;
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", card.dataset.choreId);
        });
        card.addEventListener("dragend", function () {
          draggedCard = null;
        });
      });

    document.querySelectorAll("[data-drop-target]").forEach(function (target) {
      const targetName = target.dataset.dropTarget;

      target.addEventListener("dragover", function (event) {
        if (targetName === "overdue" || !draggedCard) return;
        if (actionFor(targetName, draggedCard)) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
        }
      });

      target.addEventListener("drop", function (event) {
        if (targetName === "overdue" || !draggedCard) return;
        const action = actionFor(targetName, draggedCard);
        if (!action || !action.url) return;
        event.preventDefault();
        postAction(action);
      });
    });
  });
})();