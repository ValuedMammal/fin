
/* On page load script
function myFunc() {
    document.addEventListener('DOMContentLoaded', function() {
        // inline function
    });
} */

// Query for database symbol, quote.html
var input = document.getElementById('q0');
input.addEventListener('input', async function() {
    let response = await fetch('/search?q=' + input.value);
    let row = await response.text();
    document.querySelector('tr').innerHTML = row;
});

// Show/Hide button, advanced.html
var btn = document.getElementById('aaa');
btn.addEventListener('click', function() {
    if (btn.value == 'expand')
    {
        btn.innerHTML = 'hide';
        btn.value = 'hide';
    }
    else
    {
        btn.innerHTML = 'expand';
        btn.value = 'expand';
    }
});

// Buy: toggle dollars to spend
function buySwitch() {
    var d = document.getElementById('s-dollars');
    var s = document.getElementById('b-shares');

    // Enable $
    if (d.disabled == true)
    {
        d.disabled = false;
        s.disabled = true;
    }
    
    // Enable shares
    else
    {
        s.disabled = false;
        d.disabled = true;
    }
}

// Sell: toggle dollars to receive
function sellSwitch() {
    var d = document.getElementById('b-dollars');
    var s = document.getElementById('s-shares');
    
    // Enable $
    if (d.disabled == true)
    {
       d.disabled = false;
       s.disabled = true;
    }
    
    // Enable shares
    else
    {
       s.disabled = false;
       d.disabled = true;
    }
}
