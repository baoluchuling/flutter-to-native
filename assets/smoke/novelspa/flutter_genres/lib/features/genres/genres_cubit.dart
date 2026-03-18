class GenresCubit extends Cubit<GenresState> {
  GenresCubit() : super(const GenresState.loading());

  Future<void> loadGenres() async {}

  Future<void> refreshGenres() async {}

  Future<void> retryLoad() async {}

  void selectSort() {}

  void openSourceSheet() {}

  Future<void> loadMoreBooks() async {}
}

enum GenresStatus { loading, success, error, empty }

class GenresState {
  const GenresState.loading();
  const GenresState.success();
  const GenresState.error();
  const GenresState.empty();
}
