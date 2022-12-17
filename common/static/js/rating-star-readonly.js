$(document).ready( function() {
let render = function() {
    let ratingLabels = $(".rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true
        });
    });
};
document.body.addEventListener('htmx:load', function(evt) {
    render();
});
render();
});