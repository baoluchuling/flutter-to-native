class GenresApi {
  Future<void> getGenres() async {
    await dio.get("/genres/list");
  }

  Future<void> fetchGenreBooks() async {
    await dio.get("/genres/books");
  }
}
