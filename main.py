import json
import os

# Your file list (you can also load this from a file if needed)
task_files = [
    "tasks_FvziRqkLrEU.json",
    "tasks_HjuHHI60s44.json",
    "tasks_Z40N7b9NHTE.json"
]

def generate_files_json(files):
    with open("files.json", "w", encoding="utf-8") as f:
        json.dump(files, f, indent=2)
    print(f"✅ files.json created with {len(files)} files")

def generate_index_html():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>YouTube Task Dashboard</title>
</head>
<body>
<h1>🎬 YouTube Task Dashboard</h1>
<div id="grid"></div>

<script>
async function loadTasks() {
    const fileList = await fetch("files.json").then(res => res.json());

    const results = await Promise.all(
        fileList.map(file =>
            fetch(file).then(res => res.json()).then(data => ({file, data}))
        )
    );

    const grid = document.getElementById("grid");

    results.forEach(item => {
        const videoId = item.file.replace("tasks_", "").replace(".json", "");

        const div = document.createElement("div");
        div.innerHTML = `
            <h3>${videoId}</h3>
            <iframe width="300" height="180"
                src="https://www.youtube.com/embed/${videoId}">
            </iframe>
            <ul>
                ${item.data.map(t => `<li>${t}</li>`).join("")}
            </ul>
        `;
        grid.appendChild(div);
    });
}

loadTasks();
</script>
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("✅ index.html generated")

def main():
    generate_files_json(task_files)
    generate_index_html()

if __name__ == "__main__":
    main()