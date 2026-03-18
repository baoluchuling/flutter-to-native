import 'package:flutter/material.dart';

import 'genres_cubit.dart';

class GenresFilterPage extends StatelessWidget {
  const GenresFilterPage({super.key});

  @override
  Widget build(BuildContext context) {
    final cubit = GenresCubit();
    return Scaffold(
      appBar: AppBar(title: const Text("Genres Filter")),
      body: RefreshIndicator(
        onRefresh: cubit.refreshGenres,
        child: ListView(
          children: [
            TextButton(
              onPressed: cubit.openSourceSheet,
              child: const Text("More sources"),
            ),
            TextButton(
              onPressed: cubit.selectSort,
              child: const Text("Sort by popularity"),
            ),
            TextButton(
              onPressed: cubit.retryLoad,
              child: const Text("Retry"),
            ),
            TextButton(
              onPressed: cubit.loadMoreBooks,
              child: const Text("Load more"),
            ),
          ],
        ),
      ),
    );
  }
}
