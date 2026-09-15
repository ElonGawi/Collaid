# Next Level Challenge 2026 — Team 30

Welcome to your team's code repository! 🎉

This page is where your team will store and submit your code during **Next Level Challenge 2026**. Read this guide carefully before you start — it explains everything step by step, even if you have never used Git or GitLab before.

--- 

## 🗂️ What is this page?

This is a **GitLab repository** (often called a "repo"). Think of it as a **shared Google Drive folder, but for code**. Your whole team can access it, upload files, and update them. At the deadline, the jury will look at whatever is stored here.

You are on the page for **Team 30**. Only your team has write access (can upload files) to this repository.

---

## 💻 What is Git?

**Git** is a free tool that helps teams share and manage code. Instead of emailing files back and forth or using a USB stick, Git lets everyone on your team upload their changes to this repository from their own computer.

You will only need a few simple commands — we explain exactly what to type below.

---

## 🚀 Step-by-step guide

### ✅ Step 1 — Create a GitLab account

If you don't have a GitLab account yet:

1. Go to [gitlab.com](https://gitlab.com) and click **Register**
2. Fill in your details and verify your email address
3. Done! You will receive an email invitation to join this repository — click the link in that email to get access

---

### ✅ Step 2 — Install Git on your computer

**On Windows:**
1. Go to [git-scm.com/downloads](https://git-scm.com/downloads) and click **Download for Windows**
2. Run the installer and click "Next" on everything — the default settings are fine
3. After installing, search for **Git Bash** in your Start menu and open it — this will be your terminal for the rest of this guide

**On Mac:**
1. Open the **Terminal** app (press Cmd + Space, type "Terminal", press Enter)
2. Type `git --version` and press Enter
3. If Git is not installed yet, a popup will appear asking you to install it — click Install and follow the steps

**On Linux:**
```
sudo apt install git
```

> ✅ **Check:** Open a terminal and type `git --version` — you should see something like `git version 2.x.x`. If you do, Git is ready!

---

### ✅ Step 3 — Clone this repository (do this once)

"Cloning" means **downloading a copy of this repository to your computer** so you can add your files to it. You only need to do this once per computer.

1. Open your terminal (Git Bash on Windows, Terminal on Mac/Linux)
2. Go to the folder where you want to store your project. For example, to go to your Desktop:
```
cd Desktop
```
3. Run this command to download the repository:
```
git clone https://gitlab.com/next-level-challenge/team-30.git
```
4. A folder called `team-30` will appear on your Desktop
5. Move into that folder by running:
```
cd team-30
```

> ✅ You are now inside your team's repository folder. Any files you put here can be uploaded to GitLab.

---

### ✅ Step 4 — Add your project files

Copy or move all your project files (code, notebooks, scripts, data files, etc.) into the `team-30` folder on your computer.

> ⚠️ Do **not** include passwords, API keys, or other sensitive information in your files!

---

### ✅ Step 5 — Upload your code to GitLab

Once your files are in the `team-30` folder, run these **3 commands** in your terminal. Make sure you are inside the `team-30` folder first (if you closed the terminal, re-open it and run `cd Desktop/team-30`).

**Command 1** — Tell Git which files to include:
```
git add .
```
(The dot means "all files" — don't forget it!)

**Command 2** — Save a snapshot of your work with a short description:
```
git commit -m "Update project"
```
(You can change "Update project" to anything you like, e.g. "Add machine learning model")

**Command 3** — Upload everything to GitLab:
```
git push
```

> ✅ After running `git push`, come back to this GitLab page and refresh it. You should see your files listed here!

> 🔁 **You can push as many times as you want.** Only the last version before the deadline counts, so don't be afraid to push often!

---

### ✅ Step 6 — Verify your upload

After pushing, refresh this GitLab page. You should see your files listed in the file browser above. If you can see them — you're all set! ✅

---

## ⏰ Deadlines

| What | Deadline |
|---|---|
| 💻 Code (this repository) | **Wednesday 11 March 2026 at 15:45** |
| 📊 Pitch deck | **Wednesday 11 March 2026 at 15:45** |

> ⚠️ After 15:45, the repository will be reviewed as-is. Make sure your final code is pushed on time!

---

## 📊 How to submit your pitch deck

Your pitch deck (PowerPoint or PDF) is submitted **separately** on the Next Level Challenge website — not here on GitLab.

1. Go to 👉 [www.nextlevelchallenge.be](https://www.nextlevelchallenge.be)
2. Log in with your account
3. Go to the **Submission** tab
4. Upload your pitch deck (PDF or PowerPoint)

> ⚠️ Both your **code** (here on GitLab) and your **pitch deck** (on the website) must be submitted before **15:45 on Wednesday 11 March**!

---

## ❓ Common problems

**"Git is asking for a username and password — what do I enter?"**
Enter your GitLab email address and password. If that doesn't work, you may need to use a Personal Access Token instead of your password — ask a crew member and they'll set it up for you in 2 minutes.

**"I get an error saying 'Permission denied' or 'Repository not found'"**
You probably haven't accepted your email invitation yet. Check your inbox for an email from GitLab and click the link to accept it. If you can't find it, ask a crew member.

**"I accidentally deleted or broke something"**
Don't panic! Git keeps a full history of everything. Ask a crew member and they can restore it.

**"Two people edited the same file and now there's a conflict"**
This is called a "merge conflict". It sounds scary but it's fixable. Ask a crew member for help.

**"I don't have a terminal / I don't know how to open one"**
- Windows: search for **Git Bash** in the Start menu
- Mac: press **Cmd + Space**, type **Terminal**, press Enter
- Or just ask a crew member — they'll get you started!

---

## 🆘 Need help?

Git can be confusing if it's your first time — **please do not hesitate to ask for help!**

- 👟 Ask a **crew member** walking around the venue — they are there to help you!
- 💬 Post a message on **Slack** and someone will get back to you quickly

**Good luck and have fun! Build something amazing! 🚀**

---
*Next Level Challenge 2026 — [nextlevelchallenge.be](https://www.nextlevelchallenge.be)*