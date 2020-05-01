$(document).ready( function() {
    // readonly star rating
    let ratingLabels = $(".rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true
        });
    });
    
});