import 'package:flutter/material.dart';

import 'genres_cubit.dart';
import 'genres_filter_page.dart';

class GenresPage extends StatefulWidget {
  const GenresPage({super.key});

  @override
  State<GenresPage> createState() => _GenresPageState();
}

class _GenresPageState extends State<GenresPage> {
  final GenresCubit cubit = GenresCubit();

  @override
  void initState() {
    super.initState();
    cubit.loadGenres();
  }

  void openGenreFilter() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const GenresFilterPage()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Genres")),
      body: Column(
        children: [
          Image.asset("assets/images/genres_banner.png"),
          ListTile(
            title: const Text("Open filter"),
            onTap: openGenreFilter,
          ),
        ],
      ),
    );
  }
}
