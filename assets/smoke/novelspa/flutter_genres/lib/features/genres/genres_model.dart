class GenreFilterModel {
  final String id;
  final String title;

  const GenreFilterModel({
    required this.id,
    required this.title,
  });
}

class GenreBookResponse {
  final bool hasMore;

  const GenreBookResponse({
    required this.hasMore,
  });
}
