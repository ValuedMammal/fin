
// db search
document.addEventListener('DOMContentLoaded', function() {
    var input = document.getElementById('i0');
    input.addEventListener('input', async function() {
        let response = await fetch('/search?q=' + input.value);
        let row = await response.text();
        document.getElementById('query').innerHTML = row;
    });
});
