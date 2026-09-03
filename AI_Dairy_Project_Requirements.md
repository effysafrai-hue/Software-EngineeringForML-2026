# AI Dairy — Project Requirements

**Source:** Project Guidelines - AI Dairy  
**Course:** Software Engineering for ML — Spring 2026  
**Project grade weight:** 80%

> These guidelines describe what is required for a score of 100. You do **not** have to complete every feature. Partial completion receives partial credit for each feature.
>
> Each bug found results in **-5 points**, and each week of delay results in **-5 points**.

---

# 1. Project Proposal — 60 points

Build a **working localhost web application** that implements the proposed idea and includes everything described in the project proposal.

## 1.1 Users, Passwords & Authentication

- Implement users.
- Implement passwords.
- Implement an authentication system.
- The authentication system must be secure.

## 1.2 AI Chat

Implement a chat with an AI.

The chat must:

- Accept requests written in free speech.
- Example: the user can ask to be reminded to water a plant.
- Use the AI to determine what needs to be added to the calendar.
- The AI should be able to figure out an appropriate schedule.
- The guidelines mention importing/using the Gemini API for this functionality.

## 1.3 Ask the AI About the Schedule

The user must be able to ask the chat:

- What do I need to do today?
- What do I need to do this week?

The AI should summarize the relevant tasks for the user.

## 1.4 Manual Calendar Editing

The user must be able to:

- Open the calendar in the application.
- Change the calendar manually.
- Add/change tasks without going through the AI chat.

## 1.5 Notifications

Clients/users must receive notifications according to the schedule in their calendar.

---

# 2. Long-Term Memory — 5 points

Implement a **long-term memory system for each user**.

## 2.1 User Memory

Each user should have a persistent file/record in the database containing information such as:

- User wants.
- User preferences.
- How the user prefers the AI to communicate.
- What normally happens during the user's day.
- Whether the user prefers easy tasks or hard tasks first.
- Other information needed to personalize the experience.

## 2.2 Sign-Up Questions

You may ask the student questions during sign-up.

For example:

- What courses interest the student?
- What are the student's preferences?
- What type of task ordering does the student prefer?

The purpose is to give the AI useful information from the beginning.

## 2.3 Memory Persistence

The server must save the information necessary to make the AI as personal as possible.

The AI should not "forget" critical user preferences.

## 2.4 Memory Decision System

The database/memory system should allow the AI to decide:

- When information should be concluded and saved.
- When information should be discarded.

## 2.5 Memory Should Affect AI Behavior

The stored information must actually be used by the AI.

Example from the guidelines:

- If a user tells the AI that they feel unwell and cannot do much this week, the AI should remember this.
- The AI should take this into account when deciding what the user should do today.

**The long-term memory implementation will be checked.**

---

# 3. Robustness to Hallucinations — 5 points

The AI should be robust against hallucinations.

## 3.1 Course Database

Create a database containing:

- All courses.
- Course content.
- Course reviews.
- Course explanations.

## 3.2 Verify Course Information

Whenever the AI answers a question about a course:

- The AI must check the database first.
- The AI must not invent courses.
- The AI must not claim that a course contains material that it does not actually contain.

## 3.3 Verify Student Claims

The AI should also be robust to incorrect information in the student's text.

The AI should **not automatically treat the student's feedback as fact**.

It should check relevant information against the database when appropriate.

---

# 4. Shared Calendars — 10 points

Implement shared calendars between users.

## 4.1 Create a Shared Calendar

Users must be able to create a calendar shared with other users.

## 4.2 Shared Calendar Permissions

Users sharing a calendar must be able to:

- See each other's tasks.
- Edit the shared calendar.

## 4.3 AI Chat + Shared Calendar

Each user should be able to use their own chat to:

- Add tasks to the shared calendar.
- Alter the shared calendar.

## 4.4 Shared Calendar Long-Term Memory

Each shared calendar should have its own long-term memory/personality file.

The chat should use this memory when interacting with the shared calendar.

## 4.5 Shared Chat

The chat associated with the shared calendar should also be shared.

---

# 5. Local LLM Instead of API Calls — 10 points

Use a **local LLM** instead of relying on external AI APIs for the main AI functionality.

## 5.1 Local Model

- Download and run a local LLM.
- The project can use any open-source LLM.
- The model must be strong enough for complex conversations.
- The model should be capable of handling complex mathematical conversations when needed.
- The model should not easily hallucinate information retrieved from the database.

## 5.2 Use the Local LLM for Everything

The guidelines state that the local LLM should handle everything because:

- The project requires many AI API calls.
- Free external APIs may be too weak.
- Strong external APIs may have limited token usage.

Therefore, the local LLM should be used for the project's AI functionality rather than depending on a free external API.

## 5.3 Parallel Programming

Use parallel programming techniques for the local LLM.

## 5.4 Priority Queue

Implement a priority queue for chat requests.

The goal is for the application to work well when many students are chatting at the same time.

## 5.5 Concurrent Users

The product should continue working well when many students are using the chat simultaneously.

---

# 6. Online Forum — 10 points

Implement an online forum similar to a social network/blog.

Users should be able to share:

- Ideas.
- Achievements.
- Tips for the degree.
- Ideas for improving the application.
- Other relevant content.

---

## 6.1 Create Posts

Each client/user must be able to create a forum post.

Every post should:

- Be visible to other clients.
- Have a title.
- Have a body.
- Optionally contain images.
- Optionally contain videos.

---

## 6.2 Anonymous Posts

Users must have the option to post anonymously.

When a user chooses anonymous posting:

- Their name must not be visible to other clients.

---

## 6.3 Comments

Users must be able to comment on posts.

Comments must:

- Be visible to other clients.
- Have a body.
- Optionally contain images.
- Optionally contain videos.

---

## 6.4 Likes & Dislikes

Users must be able to:

- Like posts.
- Dislike posts.
- Like comments.
- Dislike comments.
- See how many likes each post has.
- See how many dislikes each post has.
- See how many likes each comment has.
- See how many dislikes each comment has.

Users should also have a personal area where they can:

- View their own posts.
- See their overall number of likes.
- See their overall number of dislikes.

---

## 6.5 Direct Messaging

Implement direct messaging between clients.

A user must be able to send a message to any other client.

Each direct message must:

- Be visible only to the sender and receiver.
- Have a body.
- Optionally contain images.
- Optionally contain videos.

---

## 6.6 Notifications

The web application must notify users when:

- They receive a new direct message.
- Someone likes one of their posts.
- Someone dislikes one of their posts.
- Someone likes one of their comments.
- Someone dislikes one of their comments.

---

## 6.7 Events → Calendar

A user must be able to:

1. Create/send a new event.
2. Share the event.
3. Allow another user to add the event to their own calendar.

---

## 6.8 Protection Against Spam & Abuse

The server must be protected against malicious or excessive usage.

Examples:

- A user sending 1,000 messages in a short period to overload the server.
- A user uploading huge video files to overload the database.

The system should therefore include appropriate protections against:

- Message spam.
- Excessive requests.
- Oversized media uploads.
- Attempts to overload/crash the server.

---

## 6.9 Cold Seeding

The website should start with some existing content.

Create:

- A few fake clients/users.
- A few forum posts.
- A few comments.

This provides initial content for the forum.

---

## 6.10 Real-Time Forum & Messaging

The forum should support live interaction.

Requirements:

- Sending messages should provide live feedback.
- A page refresh should **not** be necessary to see new messages.
- Chats must be saved.
- Saved chats must be retrievable.
- Users must be able to access their chat history.
- Users must receive live notifications in the web application when a new message arrives.

---

# 7. Security & Reliability

Security is important throughout the project.

The server should not be easily crashed or overloaded by malicious users.

Important areas to protect:

- Authentication.
- Passwords.
- Forum requests.
- Direct messages.
- Media uploads.
- Excessive requests.
- Large video files.
- Concurrent users.
- Database access.

The guidelines explicitly emphasize having a good security system for the online forum.

---

# 8. Complete Requirements Checklist

## Core Project — 60 points

- [ ] Working localhost web application.
- [ ] Implements the proposed idea.
- [ ] Users.
- [ ] Secure passwords.
- [ ] Secure authentication.
- [ ] AI chat.
- [ ] Free-speech requests.
- [ ] AI can translate requests into calendar tasks.
- [ ] AI can determine a schedule.
- [ ] Ask AI for today's tasks.
- [ ] Ask AI for this week's tasks.
- [ ] AI summarizes tasks.
- [ ] Manual calendar editing.
- [ ] Calendar-based notifications.

## Long-Term Memory — 5 points

- [ ] Persistent memory for every user.
- [ ] Store user wants.
- [ ] Store user preferences.
- [ ] Store preferred communication style.
- [ ] Store relevant daily routine information.
- [ ] Store task-order preferences.
- [ ] Optional/useful sign-up questions.
- [ ] Server persists important information.
- [ ] AI decides what information to save.
- [ ] AI decides what information to discard.
- [ ] AI uses stored memory in future conversations.
- [ ] Memory affects scheduling/recommendations.

## Hallucination Robustness — 5 points

- [ ] Course database.
- [ ] Course content stored.
- [ ] Course reviews stored.
- [ ] Course explanations stored.
- [ ] AI checks database before answering course questions.
- [ ] AI does not invent courses.
- [ ] AI does not invent course content.
- [ ] AI verifies student claims against the database when appropriate.

## Shared Calendars — 10 points

- [ ] Create shared calendars.
- [ ] Share calendars with other users.
- [ ] Both users can view tasks.
- [ ] Both users can edit tasks.
- [ ] Individual AI chats can modify shared calendars.
- [ ] Shared calendar has long-term memory.
- [ ] Shared calendar has a personality/memory file.
- [ ] Shared chat.

## Local LLM — 10 points

- [ ] Download local open-source LLM.
- [ ] Use local LLM for AI functionality.
- [ ] Model supports complex conversations.
- [ ] Model is capable of complex mathematical conversations when needed.
- [ ] Model minimizes hallucination when using database information.
- [ ] Parallel programming.
- [ ] Priority queue for chat.
- [ ] Support many students chatting simultaneously.

## Online Forum — 10 points

- [ ] Forum/social-network style page.
- [ ] Create posts.
- [ ] Post title.
- [ ] Post body.
- [ ] Image attachments.
- [ ] Video attachments.
- [ ] Anonymous posting.
- [ ] Anonymous names hidden from other clients.
- [ ] Comments.
- [ ] Comment body.
- [ ] Comment image attachments.
- [ ] Comment video attachments.
- [ ] Like posts.
- [ ] Dislike posts.
- [ ] Like comments.
- [ ] Dislike comments.
- [ ] Display like counts.
- [ ] Display dislike counts.
- [ ] Personal area with user's posts.
- [ ] Personal overall like count.
- [ ] Personal overall dislike count.
- [ ] Direct messaging.
- [ ] Private messages visible only to sender/receiver.
- [ ] Message image attachments.
- [ ] Message video attachments.
- [ ] New-message notifications.
- [ ] Like/dislike notifications.
- [ ] Share events.
- [ ] Add shared events to personal calendar.
- [ ] Spam protection.
- [ ] Large-file protection.
- [ ] Cold-seeded fake users.
- [ ] Cold-seeded posts.
- [ ] Cold-seeded comments.
- [ ] Real-time updates without page refresh.
- [ ] Persistent chats.
- [ ] Retrievable chat history.
- [ ] Live web-app notifications.
- [ ] Server security against malicious users.

---

# 9. Scoring Summary

| Feature | Points |
|---|---:|
| Project Proposal / Core Application | 60 |
| Long-Term Memory | 5 |
| Robustness to Hallucinations | 5 |
| Shared Calendars | 10 |
| Local LLM Instead of API Calls | 10 |
| Online Forum | 10 |
| **Total possible** | **100** |

**Important:** The guidelines state that the project is **80% of the course grade**.

Partial implementation receives partial credit, so the project does not necessarily need every feature to receive a grade.
